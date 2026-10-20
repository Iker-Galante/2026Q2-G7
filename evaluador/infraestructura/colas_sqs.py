"""Las dos colas del evaluador, por el endpoint de interfaz de SQS (la subred no tiene internet)."""

from __future__ import annotations

import json
from typing import Any

from ..puertos import Mensaje, ModeloPendiente, ResultadoEvaluacion


class ColaEvaluacionesSqs:
    def __init__(self, sqs, url: str):
        self._sqs = sqs
        self._url = url

    def recibir(self, espera_s: int) -> Mensaje | None:
        r = self._sqs.receive_message(QueueUrl=self._url, MaxNumberOfMessages=1, WaitTimeSeconds=espera_s)
        mensajes = r.get("Messages") or []
        return Mensaje(mensajes[0]["Body"], mensajes[0]["ReceiptHandle"]) if mensajes else None

    def borrar(self, m: Mensaje) -> None:
        self._sqs.delete_message(QueueUrl=self._url, ReceiptHandle=m.recibo)

    def extender(self, m: Mensaje, segundos: int) -> None:
        self._sqs.change_message_visibility(QueueUrl=self._url, ReceiptHandle=m.recibo, VisibilityTimeout=segundos)


class ResultadosSqs:
    """Publica en `resultados`. Lo que sale es agregado: métricas, versión y hash del conjunto."""

    def __init__(self, sqs, url: str, evaluador_id: str):
        self._sqs = sqs
        self._url = url
        self._yo = evaluador_id

    def _publicar(self, modelo: ModeloPendiente, cuerpo: dict[str, Any]) -> None:
        mensaje = {"tipo": "evaluacion", "modelo_id": str(modelo.id), "evaluador": self._yo, **cuerpo}
        self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps(mensaje))

    def en_curso(self, modelo: ModeloPendiente) -> None:
        self._publicar(modelo, {"estado": "en_curso"})

    def terminar_ok(self, modelo: ModeloPendiente, r: ResultadoEvaluacion) -> None:
        self._publicar(modelo, {"estado": "ok", "metricas": r.metricas, "conjunto": r.conjunto,
                                "conjunto_version": r.conjunto_version, "manifiesto": r.manifiesto,
                                "terminado": r.terminado.isoformat()})

    def terminar_error(self, modelo: ModeloPendiente, motivo: str) -> None:
        self._publicar(modelo, {"estado": "error", "error": motivo[:2000]})
