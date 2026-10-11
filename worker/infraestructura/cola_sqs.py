from __future__ import annotations

from ..puertos import Mensaje


class ColaSqs:
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
