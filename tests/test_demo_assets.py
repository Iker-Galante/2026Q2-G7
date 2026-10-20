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
    md = demo.catalogo()[0]
    contrato = (md.directorio / "modelo.json").read_bytes()
    ref = {"modelo.onnx": {"sha256": demo.sha(b"pesos"), "bytes": 5},
           "modelo.json": {"sha256": demo.sha(contrato), "bytes": len(contrato)}}
    monkeypatch.setattr(demo.ModeloDemo, "metadata", lambda self: {"archivos": ref})
    monkeypatch.setattr(demo, "modelo_local", lambda cache, modelo: {"modelo.onnx": b"pesos", "modelo.json": contrato})
    carpeta = tmp_path / "torax-rx" / "v1"
    for key, body in archivos.items():
        p = carpeta / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md])
    assert s3.escritos.index(("evaluacion", "torax-rx/v1/manifiesto.json")) > s3.escritos.index(("evaluacion", "torax-rx/v1/verdad.jsonl"))
    antes = dict(s3.objetos)
    s3.escritos.clear()
    demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md])
    assert s3.objetos == antes
    assert all(key.startswith("demo/") for _, key in s3.escritos)
    del s3.objetos["evaluacion", "torax-rx/v1/casos/000.png"]
    demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md])
    assert s3.objetos == antes
    s3.objetos["modelos", md.prefijo + "modelo.onnx"] = b"otros"
    assert not demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md])[md.clave]
    assert ("modelos", md.listo) not in s3.objetos


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
    monkeypatch.setattr(demo.ModeloDemo, "metadata", lambda self: {"archivos": {
        "modelo.onnx": {"url": "https://example.invalid/pesos", "sha256": "0" * 64, "bytes": 5}}})
    monkeypatch.setattr(demo.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"pesos"))
    with pytest.raises(ValueError):
        demo.modelo_local(tmp_path, demo.catalogo()[0])
    assert not (tmp_path / "modelo.onnx").exists()


def test_fallo_de_un_modelo_no_bloquea_los_demas(tmp_path, monkeypatch):
    modelos = demo.catalogo()
    def refs(md):
        datos = (md.directorio / "modelo.json").read_bytes()
        return {"archivos": {"modelo.onnx": {"sha256": demo.sha(b"pesos"), "bytes": 5},
                             "modelo.json": {"sha256": demo.sha(datos), "bytes": len(datos)}}}
    monkeypatch.setattr(demo.ModeloDemo, "metadata", refs)
    rutas_cache = []
    def locales(cache, md):
        rutas_cache.append(cache)
        return {"modelo.onnx": b"pesos", "modelo.json": (md.directorio / "modelo.json").read_bytes()}
    monkeypatch.setattr(demo, "modelo_local", locales)
    s3 = S3()
    for key, datos in conjunto().items():
        s3.put_object(Bucket="evaluacion", Key="torax-rx/v1/" + key, Body=datos)
    s3.put_object(Bucket="modelos", Key=modelos[0].prefijo + "modelo.onnx", Body=b"alterado")
    s3.escritos.clear()
    resultado = demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert resultado == {modelos[0].clave: False, modelos[1].clave: True, modelos[2].clave: True}
    assert len(set(rutas_cache)) == 2
    for md in modelos[1:]:
        assert ("modelos", md.listo) in s3.objetos
    assert all(b != "evaluacion" for b, _ in s3.escritos)
    # Una segunda ejecución no reescribe el conjunto compartido.
    s3.escritos.clear()
    demo.preparar(s3, "modelos", "evaluacion", tmp_path)
    assert all(b != "evaluacion" for b, _ in s3.escritos)


def test_manifiestos_y_contratos_consistentes():
    from ateneo_ml.contrato import ContratoModelo
    modelos = demo.catalogo()
    assert len(modelos) == 3
    for md in modelos:
        manifiesto = md.metadata()
        contrato = ContratoModelo.desde_json(md.contrato())
        assert (contrato.nombre, contrato.version) == (md.nombre, md.version)
        assert manifiesto["revision"] in manifiesto["archivos"]["modelo.onnx"]["url"]


def test_descarga_interrumpida_no_deja_un_onnx_instalado(tmp_path, monkeypatch):
    md = demo.catalogo()[1]
    def fallo(*args, **kwargs):
        raise TimeoutError("descarga interrumpida")
    monkeypatch.setattr(demo.urllib.request, "urlopen", fallo)
    with pytest.raises(TimeoutError):
        demo.modelo_local(tmp_path, md)
    assert not list(tmp_path.glob("*.onnx"))
    assert not list(tmp_path.glob("*.part"))


def test_estado_transitorio_permite_seguir_consultando_hasta_el_reintento(tmp_path, monkeypatch):
    md = demo.catalogo()[0]
    s3 = S3()
    monkeypatch.setattr(demo, "preparar_conjunto", lambda *args: {"hash": "verificado"})
    def fallo(*args):
        raise TimeoutError("temporal")
    monkeypatch.setattr(demo, "preparar_modelo", fallo)
    assert not demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md], final=False)[md.clave]
    assert json.loads(s3.objetos["modelos", md.estado])["estado"] == "preparando"
    demo.preparar(s3, "modelos", "evaluacion", tmp_path, [md], final=True)
    assert json.loads(s3.objetos["modelos", md.estado])["estado"] == "error"
