"""El consumidor de SQS del worker, con fakes: sin SQS, sin Postgres, sin modelo."""

from __future__ import annotations

import json

from ateneo_ml.errores import ImagenIlegible

from worker.aplicacion import Resultado
from worker.consumidor import ProcesarMensaje
from worker.puertos import Mensaje

CUERPO = json.dumps({
    "trabajo_id": "t-1",
    "modelo": {"nombre": "torax", "version": "1.0.0", "bucket": "bm", "prefix": "modelos/torax/1.0.0/"},
    "estudio": {"bucket": "be", "key": "estudios/a.png"},
})


class InferirFalso:
    def __init__(self, error: Exception | None = None):
        self.error, self.llamadas = error, 0

    def ejecutar(self, modelo, estudio):
        self.llamadas += 1
        if self.error:
            raise self.error
        return Resultado("PNEUMONIA", {"NORMAL": 0.1, "PNEUMONIA": 0.9}, 120, "worker-1")


class ColaFalsa:
    def __init__(self):
        self.borrados, self.devueltos = [], []

    def recibir(self, espera_s): return None
    def borrar(self, m): self.borrados.append(m.recibo)
    def devolver(self, m, en_s): self.devueltos.append((m.recibo, en_s))


class ResultadosFalsos:
    def __init__(self, estado="pendiente"):
        self.estado, self.error, self.resultado = estado, None, None

    def tomar(self, trabajo_id, worker):
        if self.estado not in ("pendiente", "en_curso"):
            return False
        self.estado = "en_curso"
        return True

    def terminar_ok(self, trabajo_id, worker, prediccion, probabilidades, duracion_ms):
        self.estado, self.resultado = "ok", (prediccion, worker)

    def terminar_error(self, trabajo_id, motivo):
        self.estado, self.error = "error", motivo

    def reintentar(self, trabajo_id, motivo):
        self.estado, self.error = "pendiente", motivo


def _procesar(inferir, resultados, recepciones=1, cuerpo=CUERPO):
    cola = ColaFalsa()
    ProcesarMensaje(inferir, cola, resultados, max_intentos=3, reintento_s=10).ejecutar(
        Mensaje(cuerpo=cuerpo, recibo="r-1", recepciones=recepciones))
    return cola


def test_ok_guarda_el_resultado_y_recien_entonces_borra():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(), r)
    assert r.estado == "ok" and r.resultado == ("PNEUMONIA", "worker-1")
    assert cola.borrados == ["r-1"]


def test_mensaje_repetido_de_un_trabajo_terminado_no_infiere():
    inferir, r = InferirFalso(), ResultadosFalsos(estado="ok")
    cola = _procesar(inferir, r)
    assert inferir.llamadas == 0 and cola.borrados == ["r-1"]


def test_error_definitivo_marca_error_y_borra():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(ImagenIlegible("no es una imagen")), r)
    assert r.estado == "error" and "ImagenIlegible" in r.error
    assert cola.borrados == ["r-1"]


def test_error_transitorio_vuelve_a_pendiente_y_a_la_cola():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(TimeoutError("S3 lento")), r)
    assert r.estado == "pendiente" and cola.devueltos == [("r-1", 10)] and cola.borrados == []


def test_tercer_intento_marca_error_y_deja_el_mensaje_para_la_dlq():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(TimeoutError("S3 lento")), r, recepciones=3)
    assert r.estado == "error" and "tras 3 intentos" in r.error
    assert cola.borrados == [] and cola.devueltos == []


def test_mensaje_ilegible_se_descarta():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(), r, cuerpo="no es json")
    assert cola.borrados == ["r-1"] and r.estado == "pendiente"
