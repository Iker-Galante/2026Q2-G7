from botocore.exceptions import ClientError

from ..puertos import NoEncontrado, RefObjeto


class FuenteS3:
    def __init__(self, cliente):
        self._s3 = cliente

    def leer(self, ref: RefObjeto) -> bytes:
        try:
            return self._s3.get_object(Bucket=ref.bucket, Key=ref.key)["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                raise NoEncontrado(f"no existe s3://{ref.bucket}/{ref.key}") from e
            raise
