from __future__ import annotations

import json
from typing import Any

from ..puertos import Mensaje, Resultado


class ColaSqs:
    """La cola `inferencias`, del lado del que consume."""

    def __init__(self, sqs, url: str):
        self._sqs = sqs
        self._url = url

    def recibir(self, espera_s: int) -> Mensaje | None:
        r = self._sqs.receive_message(QueueUrl=self._url, MaxNumberOfMessages=1, WaitTimeSeconds=espera_s,
                                      MessageSystemAttributeNames=["ApproximateReceiveCount"])
        mensajes = r.get("Messages") or []
        if not mensajes:
            return None
        m = mensajes[0]
        return Mensaje(cuerpo=m["Body"], recibo=m["ReceiptHandle"],
                       recepciones=int(m.get("Attributes", {}).get("ApproximateReceiveCount", "1")))

    def borrar(self, m: Mensaje) -> None:
        self._sqs.delete_message(QueueUrl=self._url, ReceiptHandle=m.recibo)

    def devolver(self, m: Mensaje, en_s: int) -> None:
        self._sqs.change_message_visibility(QueueUrl=self._url, ReceiptHandle=m.recibo, VisibilityTimeout=en_s)


class ResultadosSqs:
    """La cola `resultados`: lo que el procesador escribe en la base."""

    def __init__(self, sqs, url: str):
        self._sqs = sqs
        self._url = url

    def _publicar(self, cuerpo: dict[str, Any]) -> None:
        self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps({"tipo": "inferencia", **cuerpo}))

    def en_curso(self, trabajo_id: str, worker: str, intento: int) -> None:
        self._publicar({"trabajo_id": trabajo_id, "estado": "en_curso", "worker": worker, "intento": intento})

    def ok(self, trabajo_id: str, r: Resultado) -> None:
        self._publicar({"trabajo_id": trabajo_id, "estado": "ok", "worker": r.worker, "prediccion": r.prediccion,
                        "probabilidades": r.probabilidades, "duracion_ms": r.duracion_ms})

    def error(self, trabajo_id: str, motivo: str) -> None:
        self._publicar({"trabajo_id": trabajo_id, "estado": "error", "error": motivo[:2000]})
