from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import ClientError

from ...aplicacion.puertos import RefModeloEnBucket
from ...dominio.errores import EntradaInvalida, NoEncontrado


class CatalogoModelosS3:
    """Lo que hay subido a mano en el bucket de modelos: modelos/<nombre>/<version>/modelo.json."""

    def __init__(self, cliente, bucket: str, prefijo: str = "modelos/"):
        self._s3 = cliente
        self._bucket = bucket
        self._prefijo = prefijo

    def listar(self) -> list[RefModeloEnBucket]:
        refs: list[RefModeloEnBucket] = []
        paginador = self._s3.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=self._bucket, Prefix=self._prefijo):
            for obj in pagina.get("Contents", []):
                key: str = obj["Key"]
                if not key.endswith("/modelo.json"):
                    continue
                partes = key[len(self._prefijo):].split("/")
                if len(partes) != 3:
                    continue
                nombre, version, _ = partes
                refs.append(RefModeloEnBucket(nombre=nombre, version=version, prefix=f"{self._prefijo}{nombre}/{version}/"))
        return refs

    def leer_contrato(self, prefix: str) -> dict[str, Any]:
        key = f"{prefix}modelo.json"
        try:
            cuerpo = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                raise NoEncontrado(f"no existe {key} en {self._bucket}") from e
            raise
        try:
            return json.loads(cuerpo)
        except json.JSONDecodeError as e:
            raise EntradaInvalida(f"{key} no es JSON válido: {e}") from e
