"""Adaptador de la cola de inferencias en SQS. Traduce fallos de AWS a errores del dominio."""

from __future__ import annotations

import json

from botocore.exceptions import BotoCoreError, ClientError

from ...aplicacion.puertos import PeticionInferencia
from ...dominio.errores import ServicioNoDisponible


class ColaInferenciasSqs:
    def __init__(self, sqs, url: str):
        self._sqs = sqs
        self._url = url

    def enviar(self, p: PeticionInferencia) -> None:
        try:
            self._sqs.send_message(QueueUrl=self._url, MessageBody=json.dumps(p.como_mensaje()))
        except (BotoCoreError, ClientError) as e:
            raise ServicioNoDisponible(f"no se pudo encolar en SQS: {e}") from e
