from __future__ import annotations

from ...aplicacion.puertos import SubidaFirmada
from ...dominio.estudio import ObjetoAlmacenado
from .comun import describir_objeto, firmar_post


class AlmacenEstudiosS3:
    def __init__(self, cliente, bucket: str, url_publica: str | None = None):
        self._s3 = cliente
        self._bucket = bucket
        self._url_publica = url_publica

    def firmar_subida(self, key: str, content_type: str, max_bytes: int) -> SubidaFirmada:
        return firmar_post(self._s3, self._bucket, key, content_type, max_bytes, self._url_publica)

    def describir(self, key: str) -> ObjetoAlmacenado:
        return describir_objeto(self._s3, self._bucket, key)
