from __future__ import annotations

from urllib.parse import urlsplit

from botocore.exceptions import ClientError

from ...aplicacion.puertos import SubidaFirmada
from ...dominio.errores import NoEncontrado
from ...dominio.estudio import ObjetoAlmacenado


class AlmacenEstudiosS3:
    def __init__(self, cliente, bucket: str, url_publica: str | None = None):
        self._s3 = cliente
        self._bucket = bucket
        self._url_publica = url_publica.rstrip("/") if url_publica else None

    def firmar_subida(self, key: str, content_type: str, max_bytes: int) -> SubidaFirmada:
        firmado = self._s3.generate_presigned_post(
            Bucket=self._bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
            ExpiresIn=600,
        )
        url = firmado["url"]
        if self._url_publica:
            # Desarrollo local: el backend firma contra http://minio:9000 pero el navegador
            # llega por http://localhost:9000. La firma del POST prefirmado no incluye el host.
            partes = urlsplit(url)
            url = self._url_publica + partes.path + (f"?{partes.query}" if partes.query else "")
        return SubidaFirmada(url=url, campos=dict(firmado["fields"]))

    def describir(self, key: str) -> ObjetoAlmacenado:
        try:
            r = self._s3.head_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") in (403, 404):
                raise NoEncontrado(f"no existe {key} en {self._bucket}") from e
            raise
        return ObjetoAlmacenado(tamano_bytes=int(r["ContentLength"]), etag=r.get("ETag"))
