import hashlib
import io
import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from tools import demo_assets as demo
from tools.empaquetar_codigo import preparar as empaquetar


def conjunto():
    archivos = {}
    filas = []
    for i in range(200):
        nombre = f"{i:03}.png"
        archivos["casos/" + nombre] = f"imagen-{i}".encode()
        filas.append({"caso": nombre, "etiqueta": "NORMAL" if i < 100 else "PNEUMONIA"})
    h = hashlib.sha256()
    for f in filas:
        h.update(demo.sha(archivos["casos/" + f["caso"]]).encode())
    archivos["verdad.jsonl"] = "\n".join(json.dumps(f) for f in filas).encode()
    archivos["manifiesto.json"] = json.dumps({"casos": 200, "hash": "sha256:" + h.hexdigest()}).encode()
    return archivos


class S3:
    def __init__(self):
        self.objetos = {}
        self.escritos = []

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objetos:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objetos[Bucket, Key])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objetos[Bucket, Key] = Body
        self.escritos.append((Bucket, Key))

    def delete_object(self, Bucket, Key):
        self.objetos.pop((Bucket, Key), None)

    def upload_file(self, nombre, bucket, key):
        self.put_object(Bucket=bucket, Key=key, Body=Path(nombre).read_bytes())


def test_conjunto_incompleto_y_hash():
    archivos = conjunto()
    assert demo.validar_conjunto(archivos.__getitem__)["casos"] == 200
    archivos["casos/000.png"] = b"alterado"
    with pytest.raises(ValueError, match="hash"):
        demo.validar_conjunto(archivos.__getitem__)
    del archivos["casos/001.png"]
    with pytest.raises(KeyError):
        demo.validar_conjunto(archivos.__getitem__)


def test_idempotencia_y_reparacion_sin_descarga(tmp_path, monkeypatch):
    s3 = S3()
    archivos = conjunto()
    contrato = (demo.MODELO_DIR / "modelo.json").read_bytes()
    ref = {"modelo.onnx": {"sha256": demo.sha(b"pesos"), "bytes": 5},
           "modelo.json": {"sha256": demo.sha(contrato), "bytes": len(contrato)}}
    monkeypatch.setattr(demo, "manifiesto_modelo", lambda: {"archivos": ref})
    monkeypatch.setattr(demo, "modelo_local", lambda cache: {"modelo.onnx": b"pesos", "modelo.json": contrato})
    carpeta = tmp_path / "torax-rx" / "v1"
    for key, body in archivos.items():
        p = carpeta / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert s3.escritos.index(("evaluacion", "torax-rx/v1/manifiesto.json")) > s3.escritos.index(("evaluacion", "torax-rx/v1/verdad.jsonl"))
    antes = dict(s3.objetos)
    s3.escritos.clear()
    demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert s3.objetos == antes
    assert all(key.startswith("demo/") for _, key in s3.escritos)
    del s3.objetos["evaluacion", "torax-rx/v1/casos/000.png"]
    demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert s3.objetos == antes
    s3.objetos["modelos", demo.PREFIJO + "modelo.onnx"] = b"otros"
    with pytest.raises(ValueError, match="SHA-256"):
        demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert ("modelos", demo.LISTO) not in s3.objetos


def test_empaquetado_binario_y_lista_explicita(tmp_path):
    raiz, salida = tmp_path / "repo", tmp_path / "salida"
    raiz.mkdir()
    binario = b"\x00\xff\x80ONNX"
    (raiz / "modelo.onnx").write_bytes(binario)
    (raiz / "secreto.env").write_text("no incluir")
    empaquetar(raiz, salida, ["modelo.onnx"])
    assert (salida / "modelo.onnx").read_bytes() == binario
    assert not (salida / "secreto.env").exists()
    with pytest.raises(ValueError):
        empaquetar(raiz, salida, ["../fuera"])


def test_descarga_rechaza_hash_incorrecto(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "manifiesto_modelo", lambda: {"archivos": {
        "modelo.onnx": {"url": "https://example.invalid/pesos", "sha256": "0" * 64, "bytes": 5}}})
    monkeypatch.setattr(demo.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"pesos"))
    with pytest.raises(ValueError):
        demo.modelo_local(tmp_path)
    assert not (tmp_path / "modelo.onnx").exists()
