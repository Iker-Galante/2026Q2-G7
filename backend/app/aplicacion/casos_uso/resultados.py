"""El procesador aplica lo que el worker y el evaluador publican en la cola `resultados`.

Es el único que escribe resultados en la base: las capas que corren modelos de terceros no
tienen credenciales. Cada mensaje se aplica solo si el registro todavía no terminó, así que
una entrega repetida de SQS (que entrega al menos una vez) no cambia nada.

Los mensajes:
  {"tipo": "inferencia", "trabajo_id", "estado": "en_curso", "worker", "intento"}
  {"tipo": "inferencia", "trabajo_id", "estado": "ok", "worker", "prediccion", "probabilidades", "duracion_ms"}
  {"tipo": "inferencia", "trabajo_id", "estado": "error", "error"}
  {"tipo": "evaluacion", "modelo_id", "estado": "en_curso", "evaluador"}
  {"tipo": "evaluacion", "modelo_id", "estado": "ok", "evaluador", "metricas", "conjunto",
   "conjunto_version", "manifiesto", "terminado"}
  {"tipo": "evaluacion", "modelo_id", "estado": "error", "evaluador", "error"}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from ...dominio.modelo import ResultadoEvaluacion
from ...dominio.trabajo import ResultadoInferencia
from ..puertos import RegistroResultados


class MensajeInvalido(Exception):
    """Un mensaje que no se puede aplicar nunca: se descarta en vez de reintentarlo."""


class AplicarResultado:
    def __init__(self, registro: RegistroResultados):
        self._registro = registro

    def ejecutar(self, cuerpo: dict[str, Any]) -> bool:
        """True si cambió algo; False si el registro ya había terminado (un duplicado)."""
        try:
            tipo = cuerpo["tipo"]
            if tipo == "inferencia":
                return self._inferencia(cuerpo)
            if tipo == "evaluacion":
                return self._evaluacion(cuerpo)
        except (KeyError, TypeError, ValueError) as e:
            raise MensajeInvalido(f"{e.__class__.__name__}: {e}") from e
        raise MensajeInvalido(f"tipo desconocido: {tipo!r}")

    def _inferencia(self, c: dict[str, Any]) -> bool:
        trabajo_id = UUID(c["trabajo_id"])
        estado = c["estado"]
        if estado == "en_curso":
            return self._registro.inferencia_en_curso(trabajo_id, str(c["worker"]), int(c.get("intento", 1)))
        if estado == "ok":
            return self._registro.inferencia_terminada(trabajo_id, ResultadoInferencia(
                prediccion=str(c["prediccion"]),
                probabilidades={str(k): float(v) for k, v in c["probabilidades"].items()},
                worker_id=str(c["worker"]),
                duracion_ms=int(c["duracion_ms"]),
            ))
        if estado == "error":
            return self._registro.inferencia_fallida(trabajo_id, str(c["error"])[:2000])
        raise MensajeInvalido(f"estado de inferencia desconocido: {estado!r}")

    def _evaluacion(self, c: dict[str, Any]) -> bool:
        modelo_id = UUID(c["modelo_id"])
        evaluador = str(c["evaluador"])
        estado = c["estado"]
        if estado == "en_curso":
            return self._registro.evaluacion_en_curso(modelo_id, evaluador)
        if estado == "ok":
            metricas = dict(c["metricas"])
            float(metricas["accuracy"])                         # sin accuracy no hay qué mostrar en el catálogo
            return self._registro.evaluacion_terminada(modelo_id, ResultadoEvaluacion(
                metricas=metricas,
                conjunto=str(c["conjunto"]),
                conjunto_version=str(c["conjunto_version"]),
                manifiesto=dict(c.get("manifiesto") or {}),
                evaluador_id=evaluador,
                evaluado_en=datetime.fromisoformat(c["terminado"]),
            ))
        if estado == "error":
            return self._registro.evaluacion_fallida(modelo_id, evaluador, str(c["error"])[:2000])
        raise MensajeInvalido(f"estado de evaluación desconocido: {estado!r}")
