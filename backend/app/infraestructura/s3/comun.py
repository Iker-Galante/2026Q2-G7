"""Lo que comparten los dos adaptadores de S3: firmar una subida y mirar un objeto.

Estaba duplicado en el almacén de estudios y en el catálogo de modelos; los dos
suben archivos que el navegador manda directo al bucket, así que la firma del
POST prefirmado y el `head_object` viven acá una sola vez.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from botocore.exceptions import ClientError

from ...aplicacion.puertos import SubidaFirmada
from ...dominio.errores import NoEncontrado
from ...dominio.estudio import ObjetoAlmacenado

EXPIRACION_S = 600


def firmar_post(cliente, bucket: str, key: str, content_type: str, max_bytes: int,
                url_publica: str | None = None) -> SubidaFirmada:
    """POST prefirmado a `key`, atado al content type y al tamaño máximo."""
    firmado = cliente.generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
        ExpiresIn=EXPIRACION_S,
    )
    url = firmado["url"]
    if url_publica:
        # Desarrollo local: el backend firma contra http://minio:9000 pero el navegador
        # llega por http://localhost:9000. La firma del POST prefirmado no incluye el host.
        partes = urlsplit(url)
        url = url_publica.rstrip("/") + partes.path + (f"?{partes.query}" if partes.query else "")
    return SubidaFirmada(url=url, campos=dict(firmado["fields"]))


def describir_objeto(cliente, bucket: str, key: str) -> ObjetoAlmacenado:
    """Tamaño y etag de un objeto ya subido. `NoEncontrado` si todavía no está."""
    try:
        r = cliente.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") in (403, 404):
            raise NoEncontrado(f"no existe {key} en {bucket}") from e
        raise
    return ObjetoAlmacenado(tamano_bytes=int(r["ContentLength"]), etag=r.get("ETag"))
