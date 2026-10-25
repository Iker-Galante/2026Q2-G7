from __future__ import annotations

import logging
from pathlib import Path

from botocore.exceptions import ClientError

from ateneo_ml import ContratoInvalido

log = logging.getLogger(__name__)


class ModeloS3:
    def __init__(self, cliente, bucket: str):
        self._s3 = cliente
        self._bucket = bucket

    def descargar(self, s3_prefix: str, destino: Path) -> Path:
        destino.mkdir(parents=True, exist_ok=True)
        for archivo in ("modelo.json", "modelo.onnx"):
            key = f"{s3_prefix}{archivo}"
            log.info("bajando s3://%s/%s", self._bucket, key)
            try:
                self._s3.download_file(self._bucket, key, str(destino / archivo))
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                    raise ContratoInvalido(f"falta s3://{self._bucket}/{key}") from e
                raise
        return destino
