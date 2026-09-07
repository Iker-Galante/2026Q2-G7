"""El evaluador con fakes: sin S3, sin Postgres, con el ONNX diminuto."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from uuid import uuid4

from PIL import Image

from evaluador.aplicacion import EvaluarModelo
from evaluador.puertos import Caso, Conjunto, ModeloPendiente


def _png(color):
    img = Image.new("RGB", (4, 4), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ColaFalsa:
    def __init__(self):
        self.ok = None
        self.error = None

    def reencolar_en_curso(self): return 0
    def tomar_pendiente(self): return None
    def terminar_ok(self, modelo, r): self.ok = r
    def terminar_error(self, modelo, motivo): self.error = motivo


class ConjuntoFalso:
    def __init__(self, casos: dict[str, tuple[str, bytes]], manifiesto=None):
        self._casos = casos          # nombre → (etiqueta, bytes)
        self._manifiesto = manifiesto or {"casos": len(casos), "hash": "sha256:x"}

    def ultima_version(self, tipo): return "v2"
    def cargar(self, tipo, version):
        return Conjunto(tipo, version, self._manifiesto, [Caso(n, e) for n, (e, _) in self._casos.items()])
    def leer_caso(self, conjunto, caso): return self._casos[caso.nombre][1]
    def listar_casos(self, tipo, version): return iter(self._casos.keys())


class DescargadorFalso:
    def __init__(self, onnx: Path, contrato: dict):
        self._onnx, self._contrato = onnx, contrato

    def descargar(self, prefix, destino: Path):
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy(self._onnx, destino / "modelo.onnx")
        (destino / "modelo.json").write_text(json.dumps(self._contrato))
        return destino


def _modelo():
    return ModeloPendiente(uuid4(), "prueba", "1.0.0", "torax-rx", "modelos/prueba/1.0.0/", ["NORMAL", "PNEUMONIA"])


def test_evaluacion_ok(contrato_dict, onnx_diminuto, tmp_path):
    # rojo → NORMAL, verde → PNEUMONIA (canal 1); 4 casos, uno mal etiquetado a propósito
    casos = {
        "a.png": ("NORMAL", _png((255, 0, 0))),
        "b.png": ("NORMAL", _png((255, 0, 0))),
        "c.png": ("PNEUMONIA", _png((0, 255, 0))),
        "d.png": ("PNEUMONIA", _png((255, 0, 0))),   # el modelo dirá NORMAL → 1 error
    }
    cola = ColaFalsa()
    EvaluarModelo(cola, ConjuntoFalso(casos), DescargadorFalso(onnx_diminuto, contrato_dict),
                  str(tmp_path / "trabajo"), 0.05, hilos=1).ejecutar(_modelo())
    assert cola.error is None
    assert cola.ok.metricas["accuracy"] == 0.75
    assert cola.ok.conjunto_version == "v2" and cola.ok.manifiesto["hash"] == "sha256:x"
    assert "auc" in cola.ok.metricas
    assert not (tmp_path / "trabajo" / "prueba-1.0.0").exists()      # se limpió


def test_conjunto_inconsistente_termina_en_error(contrato_dict, onnx_diminuto, tmp_path):
    casos = {"a.png": ("NORMAL", _png((255, 0, 0)))}
    cola = ColaFalsa()
    EvaluarModelo(cola, ConjuntoFalso(casos, manifiesto={"casos": 99}), DescargadorFalso(onnx_diminuto, contrato_dict),
                  str(tmp_path), 0.05, hilos=1).ejecutar(_modelo())
    assert cola.ok is None and "99" in cola.error


def test_etiqueta_desconocida_termina_en_error(contrato_dict, onnx_diminuto, tmp_path):
    casos = {"a.png": ("TUMOR", _png((255, 0, 0)))}
    cola = ColaFalsa()
    EvaluarModelo(cola, ConjuntoFalso(casos), DescargadorFalso(onnx_diminuto, contrato_dict),
                  str(tmp_path), 0.05, hilos=1).ejecutar(_modelo())
    assert "TUMOR" in cola.error


def test_demasiados_casos_ilegibles(contrato_dict, onnx_diminuto, tmp_path):
    casos = {"a.png": ("NORMAL", _png((255, 0, 0))), "b.png": ("NORMAL", b"basura")}
    cola = ColaFalsa()
    EvaluarModelo(cola, ConjuntoFalso(casos), DescargadorFalso(onnx_diminuto, contrato_dict),
                  str(tmp_path), 0.05, hilos=1).ejecutar(_modelo())
    assert "no se pudieron procesar" in cola.error
