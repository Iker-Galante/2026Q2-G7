"""Adaptador de una cola de SQS. Traduce fallos de AWS a errores del dominio.

`enviar` sirve a ColaInferencias y a ColaEvaluaciones (manda `como_mensaje()` en JSON);
`recibir` y `borrar` los usa el bucle del procesador sobre la cola `resultados`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError

from ...dominio.errores import ServicioNoDisponible


class ConMensaje(Protocol):
    def como_mensaje(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class MensajeRecibido:
    cuerpo: str
    recibo: str


class ColaSqs:
    def __init__(self, sqs, url: str):
        self._sqs = sqs
        self._url = url

    def enviar(self, p: ConMensaje) -> None:
        try:
            self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps(p.como_mensaje()))
        except (BotoCoreError, ClientError) as e:
            raise ServicioNoDisponible(f"no se pudo encolar en SQS: {e}") from e

    def recibir(self, espera_s: int, maximo: int = 10) -> list[MensajeRecibido]:
        r = self._sqs.receive_message(QueueUrl=self._url, MaxNumberOfMessages=maximo, WaitTimeSeconds=espera_s)
        return [MensajeRecibido(m["Body"], m["ReceiptHandle"]) for m in r.get("Messages") or []]

    def borrar(self, m: MensajeRecibido) -> None:
        self._sqs.delete_message(QueueUrl=self._url, ReceiptHandle=m.recibo)
