"""El consumidor del worker, con fakes: sin SQS, sin modelo. El worker no tiene base: publica."""

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
    """La cola `resultados`: guarda lo publicado, en orden."""

    def __init__(self):
        self.publicados = []

    def en_curso(self, trabajo_id, worker, intento):
        self.publicados.append(("en_curso", intento))

    def ok(self, trabajo_id, r):
        self.publicados.append(("ok", r.prediccion))

    def error(self, trabajo_id, motivo):
        self.publicados.append(("error", motivo))


def _procesar(inferir, resultados, recepciones=1, cuerpo=CUERPO):
    cola = ColaFalsa()
    ProcesarMensaje(inferir, cola, resultados, max_intentos=3, reintento_s=10).ejecutar(
        Mensaje(cuerpo=cuerpo, recibo="r-1", recepciones=recepciones))
    return cola


def test_ok_publica_el_resultado_y_recien_entonces_borra():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(), r)
    assert r.publicados == [("en_curso", 1), ("ok", "PNEUMONIA")]
    assert cola.borrados == ["r-1"]


def test_error_definitivo_publica_el_error_y_borra():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(ImagenIlegible("no es una imagen")), r)
    assert r.publicados[-1][0] == "error" and "ImagenIlegible" in r.publicados[-1][1]
    assert cola.borrados == ["r-1"]


def test_error_transitorio_devuelve_el_mensaje_sin_publicar_un_final():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(TimeoutError("S3 lento")), r, recepciones=2)
    assert r.publicados == [("en_curso", 2)]
    assert cola.devueltos == [("r-1", 10)] and cola.borrados == []


def test_tercer_intento_publica_el_error_y_deja_el_mensaje_para_la_dlq():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(TimeoutError("S3 lento")), r, recepciones=3)
    assert r.publicados[-1][0] == "error" and "tras 3 intentos" in r.publicados[-1][1]
    assert cola.borrados == [] and cola.devueltos == []


def test_mensaje_ilegible_se_descarta_sin_publicar():
    r = ResultadosFalsos()
    cola = _procesar(InferirFalso(), r, cuerpo="no es json")
    assert cola.borrados == ["r-1"] and r.publicados == []
