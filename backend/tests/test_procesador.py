"""El procesador: aplicar resultados una sola vez, descartar lo ilegible y no perder nada si la base falla."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.aplicacion.casos_uso.modelos import VencerEvaluaciones
from app.aplicacion.casos_uso.resultados import AplicarResultado, MensajeInvalido
from app.infraestructura.sqs.colas import MensajeRecibido
from app.procesador import procesar


class RegistroMemoria:
    """Como el de Postgres: cada cambio aplica solo si el registro sigue pendiente o en_curso."""

    def __init__(self):
        self.trabajos: dict = {}
        self.modelos: dict = {}

    def _cambiar(self, tabla, id, **campos):
        actual = tabla.setdefault(id, {"estado": "pendiente"})
        if actual["estado"] not in ("pendiente", "en_curso"):
            return False
        actual.update(campos)
        return True

    def inferencia_en_curso(self, trabajo_id, worker, intento):
        return self._cambiar(self.trabajos, trabajo_id, estado="en_curso", worker=worker, intento=intento)

    def inferencia_terminada(self, trabajo_id, r):
        return self._cambiar(self.trabajos, trabajo_id, estado="ok", resultado=r)

    def inferencia_fallida(self, trabajo_id, motivo):
        return self._cambiar(self.trabajos, trabajo_id, estado="error", error=motivo)

    def evaluacion_en_curso(self, modelo_id, evaluador):
        return self._cambiar(self.modelos, modelo_id, estado="en_curso", evaluador=evaluador)

    def evaluacion_terminada(self, modelo_id, r):
        return self._cambiar(self.modelos, modelo_id, estado="ok", resultado=r)

    def evaluacion_fallida(self, modelo_id, evaluador, motivo):
        return self._cambiar(self.modelos, modelo_id, estado="error", error=motivo)


def _inferencia_ok(trabajo_id):
    return {"tipo": "inferencia", "trabajo_id": str(trabajo_id), "estado": "ok", "worker": "w-1",
            "prediccion": "PNEUMONIA", "probabilidades": {"NORMAL": 0.1, "PNEUMONIA": 0.9}, "duracion_ms": 120}


def _evaluacion_ok(modelo_id):
    return {"tipo": "evaluacion", "modelo_id": str(modelo_id), "estado": "ok", "evaluador": "tarea-1",
            "metricas": {"accuracy": 0.75, "n_casos": 4}, "conjunto": "torax-rx", "conjunto_version": "v1",
            "manifiesto": {"casos": 4}, "terminado": "2026-10-15T12:00:00+00:00"}


def test_inferencia_en_curso_y_despues_ok():
    registro, t = RegistroMemoria(), uuid4()
    aplicar = AplicarResultado(registro)
    assert aplicar.ejecutar({"tipo": "inferencia", "trabajo_id": str(t), "estado": "en_curso",
                             "worker": "w-1", "intento": 2})
    assert registro.trabajos[t]["intento"] == 2
    assert aplicar.ejecutar(_inferencia_ok(t))
    r = registro.trabajos[t]["resultado"]
    assert registro.trabajos[t]["estado"] == "ok" and r.prediccion == "PNEUMONIA" and r.duracion_ms == 120


def test_un_resultado_repetido_no_cambia_nada():
    registro, t = RegistroMemoria(), uuid4()
    aplicar = AplicarResultado(registro)
    assert aplicar.ejecutar(_inferencia_ok(t)) is True
    assert aplicar.ejecutar({"tipo": "inferencia", "trabajo_id": str(t), "estado": "error", "error": "tarde"}) is False
    assert registro.trabajos[t]["estado"] == "ok"


def test_evaluacion_ok_trae_las_metricas_agregadas():
    registro, m = RegistroMemoria(), uuid4()
    assert AplicarResultado(registro).ejecutar(_evaluacion_ok(m))
    r = registro.modelos[m]["resultado"]
    assert r.accuracy == 0.75 and r.conjunto_version == "v1" and r.evaluado_en.year == 2026


@pytest.mark.parametrize("cuerpo", [
    {"tipo": "otro"},
    {"tipo": "inferencia", "trabajo_id": "no-es-uuid", "estado": "ok"},
    {"tipo": "inferencia", "trabajo_id": str(uuid4()), "estado": "raro"},
    {"tipo": "evaluacion", "modelo_id": str(uuid4()), "estado": "ok", "evaluador": "x", "metricas": {}},
    {},
])
def test_mensajes_invalidos(cuerpo):
    with pytest.raises(MensajeInvalido):
        AplicarResultado(RegistroMemoria()).ejecutar(cuerpo)


class ColaFalsa:
    def __init__(self):
        self.borrados = []

    def borrar(self, m):
        self.borrados.append(m.recibo)


def test_procesar_borra_lo_aplicado_y_lo_ilegible():
    cola, aplicar = ColaFalsa(), AplicarResultado(RegistroMemoria())
    procesar(MensajeRecibido(json.dumps(_inferencia_ok(uuid4())), "r-1"), aplicar, cola)
    procesar(MensajeRecibido("no es json", "r-2"), aplicar, cola)
    procesar(MensajeRecibido(json.dumps({"tipo": "otro"}), "r-3"), aplicar, cola)
    assert cola.borrados == ["r-1", "r-2", "r-3"]


def test_procesar_no_borra_si_la_base_falla():
    class RegistroCaido(RegistroMemoria):
        def inferencia_terminada(self, trabajo_id, r):
            raise ConnectionError("RDS no contesta")

    cola = ColaFalsa()
    with pytest.raises(ConnectionError):
        procesar(MensajeRecibido(json.dumps(_inferencia_ok(uuid4())), "r-1"), AplicarResultado(RegistroCaido()), cola)
    assert cola.borrados == []        # SQS lo vuelve a entregar


def test_vencer_evaluaciones_usa_el_plazo_configurado():
    class SinNoticias:
        def vencer_en_curso(self, minutos, motivo):
            self.args = (minutos, motivo)
            return 1

    sin_noticias = SinNoticias()
    assert VencerEvaluaciones(sin_noticias, 120).ejecutar() == 1
    assert sin_noticias.args[0] == 120 and "evaluador" in sin_noticias.args[1]
