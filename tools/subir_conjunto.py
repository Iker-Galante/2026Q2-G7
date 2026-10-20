#!/usr/bin/env python3
"""Sube una carpeta de conjunto de evaluación a S3 (o a MinIO en local).

  BUCKET_EVALUACION=ateneo-evaluacion python tools/subir_conjunto.py ./tmp/torax-rx/v1

En AWS el conjunto real conviene subirlo por la consola web (guía §04, «Add folder»), que
sube en paralelo y no depende del giga de CloudShell. Este script existe para el desarrollo
local y para conjuntos chicos.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("carpeta", help="p. ej. ./tmp/torax-rx/v1")
    p.add_argument("--bucket", default=os.environ.get("BUCKET_EVALUACION"))
    p.add_argument("--conjunto", default=None, help="por defecto, la carpeta padre")
    p.add_argument("--version", default=None, help="por defecto, el nombre de la carpeta")
    a = p.parse_args()
    if not a.bucket:
        raise SystemExit("falta --bucket o BUCKET_EVALUACION")

    import boto3
    from botocore.config import Config

    base = Path(a.carpeta)
    conjunto = a.conjunto or base.parent.name
    version = a.version or base.name
    s3 = boto3.client("s3", config=Config(
        s3={"addressing_style": "path" if os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("AWS_ENDPOINT_URL") else "auto"}))

    n = 0
    for archivo in sorted(base.rglob("*")):
        if archivo.is_file():
            key = f"{conjunto}/{version}/{archivo.relative_to(base).as_posix()}"
            s3.upload_file(str(archivo), a.bucket, key)
            n += 1
            if n % 50 == 0:
                print(f"  {n} archivos…")
    print(f"listo: {n} archivos en s3://{a.bucket}/{conjunto}/{version}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
