"""El evaluador con fakes: sin S3, sin SQS, con el ONNX diminuto."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from uuid import uuid4

from PIL import Image

from evaluador.aplicacion import EvaluarModelo
from evaluador.consumidor import ConsumidorEvaluaciones, MensajeInvalido, modelo_de
from evaluador.puertos import Caso, Conjunto, Mensaje, ModeloPendiente


def _png(color):
    img = Image.new("RGB", (4, 4), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ColaFalsa:
    """Hace de la cola `resultados`: lo que el evaluador publica."""

    def __init__(self):
        self.en_curso_visto = False
        self.ok = None
        self.error = None

    def en_curso(self, modelo): self.en_curso_visto = True
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
    assert cola.error is None and cola.en_curso_visto
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


# ---- el consumidor de la cola `evaluaciones` -----------------------------------------

def _mensaje(modelo_id=None, **cambios):
    d = {"tipo": "evaluar_modelo", "modelo_id": str(modelo_id or uuid4()), "nombre": "prueba", "version": "1.0.0",
         "tipo_estudio": "torax-rx", "prefix": "modelos/prueba/1.0.0/", "etiquetas": ["NORMAL", "PNEUMONIA"]}
    d.update(cambios)
    return json.dumps(d)


class ColaEvaluacionesFalsa:
    def __init__(self, cuerpos):
        self.pendientes = [Mensaje(c, f"r-{i}") for i, c in enumerate(cuerpos)]
        self.borrados, self.extendidos = [], []

    def recibir(self, espera_s): return self.pendientes.pop(0) if self.pendientes else None
    def borrar(self, m): self.borrados.append(m.recibo)
    def extender(self, m, segundos): self.extendidos.append((m.recibo, segundos))


class EvaluarFalso:
    def __init__(self):
        self.evaluados = []

    def ejecutar(self, modelo): self.evaluados.append(modelo)


def test_modelo_de_lee_el_mensaje_de_la_api():
    m = modelo_de(_mensaje())
    assert m.s3_prefix == "modelos/prueba/1.0.0/" and m.etiquetas == ["NORMAL", "PNEUMONIA"]


def test_consumidor_evalua_y_recien_entonces_borra():
    cola, evaluar = ColaEvaluacionesFalsa([_mensaje()]), EvaluarFalso()
    consumidor = ConsumidorEvaluaciones(cola, evaluar, 0, latido_s=60, visibilidad_s=1800)
    assert consumidor.una_vuelta() is True
    assert len(evaluar.evaluados) == 1 and cola.borrados == ["r-0"]
    assert consumidor.una_vuelta() is False                       # cola vacía


def test_consumidor_descarta_lo_ilegible_sin_evaluar():
    cola, evaluar = ColaEvaluacionesFalsa(["no es json", _mensaje(tipo="ingerir_conjunto")]), EvaluarFalso()
    consumidor = ConsumidorEvaluaciones(cola, evaluar, 0, latido_s=60, visibilidad_s=1800)
    consumidor.una_vuelta()
    consumidor.una_vuelta()
    assert evaluar.evaluados == [] and cola.borrados == ["r-0", "r-1"]


def test_si_falla_la_publicacion_el_mensaje_no_se_borra():
    class EvaluarQuePierde:
        def ejecutar(self, modelo): raise ConnectionError("SQS no contesta")

    cola = ColaEvaluacionesFalsa([_mensaje()])
    consumidor = ConsumidorEvaluaciones(cola, EvaluarQuePierde(), 0, latido_s=60, visibilidad_s=1800)
    try:
        consumidor.una_vuelta()
    except ConnectionError:
        pass
    assert cola.borrados == []


def test_el_latido_extiende_la_visibilidad_mientras_evalua():
    import time

    class EvaluarLento:
        def ejecutar(self, modelo): time.sleep(0.25)

    cola = ColaEvaluacionesFalsa([_mensaje()])
    ConsumidorEvaluaciones(cola, EvaluarLento(), 0, latido_s=0.05, visibilidad_s=1800).una_vuelta()
    assert cola.extendidos and all(e == ("r-0", 1800) for e in cola.extendidos)


def test_mensaje_sin_campos_es_invalido():
    import pytest
    with pytest.raises(MensajeInvalido):
        modelo_de(json.dumps({"tipo": "evaluar_modelo"}))
