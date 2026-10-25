from __future__ import annotations

import json
from typing import Any

from botocore.exceptions import ClientError

from ...aplicacion.puertos import RefModeloEnBucket, SubidaFirmada
from ...dominio.errores import EntradaInvalida, NoEncontrado
from ...dominio.estudio import ObjetoAlmacenado
from .comun import describir_objeto, firmar_post

# El layout del bucket vive acá y en ningún otro lado: los casos de uso hablan
# de prefijos, este adaptador sabe qué archivos hay adentro de cada uno.
ARCHIVO_MODELO = "modelo.onnx"
ARCHIVO_CONTRATO = "modelo.json"
CONTENT_TYPE_MODELO = "application/octet-stream"


class CatalogoModelosS3:
    """El bucket de modelos: modelos/<nombre>/<version>/{modelo.onnx, modelo.json}."""

    def __init__(self, cliente, bucket: str, prefijo: str = "modelos/", url_publica: str | None = None):
        self._s3 = cliente
        self._bucket = bucket
        self._prefijo = prefijo
        self._url_publica = url_publica

    def listar(self) -> list[RefModeloEnBucket]:
        refs: list[RefModeloEnBucket] = []
        paginador = self._s3.get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=self._bucket, Prefix=self._prefijo):
            for obj in pagina.get("Contents", []):
                key: str = obj["Key"]
                if not key.endswith(f"/{ARCHIVO_CONTRATO}"):
                    continue
                partes = key[len(self._prefijo):].split("/")
                if len(partes) != 3:
                    continue
                nombre, version, _ = partes
                refs.append(RefModeloEnBucket(nombre=nombre, version=version, prefix=f"{self._prefijo}{nombre}/{version}/"))
        return refs

    def leer_contrato(self, prefix: str) -> dict[str, Any]:
        key = f"{prefix}{ARCHIVO_CONTRATO}"
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

    def existe(self, prefix: str) -> bool:
        """¿El prefijo ya tiene algo? Una versión publicada no se pisa."""
        r = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix, MaxKeys=1)
        return int(r.get("KeyCount", 0)) > 0

    def firmar_subida(self, prefix: str, max_bytes: int) -> SubidaFirmada:
        """POST prefirmado del ONNX: el archivo va del navegador a S3, sin pasar por la API."""
        return firmar_post(self._s3, self._bucket, f"{prefix}{ARCHIVO_MODELO}", CONTENT_TYPE_MODELO,
                           max_bytes, self._url_publica)

    def describir_modelo(self, prefix: str) -> ObjetoAlmacenado:
        return describir_objeto(self._s3, self._bucket, f"{prefix}{ARCHIVO_MODELO}")

    def escribir_contrato(self, prefix: str, contrato: dict[str, Any]) -> None:
        """Escribe el modelo.json ya validado, al lado del ONNX."""
        self._s3.put_object(
            Bucket=self._bucket,
            Key=f"{prefix}{ARCHIVO_CONTRATO}",
            Body=json.dumps(contrato, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
