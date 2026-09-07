"""El conjunto reservado, leído por el endpoint de la VPC. Los casos no tocan el disco."""

from __future__ import annotations

import json
import re
from typing import Iterator

from botocore.exceptions import ClientError

from ..puertos import Caso, Conjunto, ConjuntoInvalido

VERSION = re.compile(r"^v(\d+)$")


class ConjuntoS3:
    def __init__(self, cliente, bucket: str):
        self._s3 = cliente
        self._bucket = bucket

    def ultima_version(self, tipo_estudio: str) -> str | None:
        r = self._s3.list_objects_v2(Bucket=self._bucket, Prefix=f"{tipo_estudio}/", Delimiter="/")
        versiones = []
        for p in r.get("CommonPrefixes", []):
            nombre = p["Prefix"].rstrip("/").split("/")[-1]
            m = VERSION.match(nombre)
            if m:
                versiones.append((int(m.group(1)), nombre))
        return max(versiones)[1] if versiones else None

    def cargar(self, tipo_estudio: str, version: str) -> Conjunto:
        base = f"{tipo_estudio}/{version}/"
        manifiesto = json.loads(self._leer(f"{base}manifiesto.json"))
        casos: list[Caso] = []
        for numero, linea in enumerate(self._leer(f"{base}verdad.jsonl").decode("utf-8").splitlines(), start=1):
            if not linea.strip():
                continue
            try:
                d = json.loads(linea)
                casos.append(Caso(nombre=str(d["caso"]), etiqueta=str(d["etiqueta"])))
            except (ValueError, KeyError) as e:
                raise ConjuntoInvalido(f"verdad.jsonl línea {numero} inválida: {e}") from e
        return Conjunto(tipo_estudio=tipo_estudio, version=version, manifiesto=manifiesto, casos=casos)

    def leer_caso(self, conjunto: Conjunto, caso: Caso) -> bytes:
        return self._leer(f"{conjunto.tipo_estudio}/{conjunto.version}/casos/{caso.nombre}")

    def listar_casos(self, tipo_estudio: str, version: str) -> Iterator[str]:
        prefijo = f"{tipo_estudio}/{version}/casos/"
        for pagina in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefijo):
            for obj in pagina.get("Contents", []):
                yield obj["Key"][len(prefijo):]

    def _leer(self, key: str) -> bytes:
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as e:
            codigo = e.response.get("Error", {}).get("Code")
            if codigo in ("NoSuchKey", "404", "NotFound"):
                raise ConjuntoInvalido(f"falta s3://{self._bucket}/{key}") from e
            if codigo == "AccessDenied":
                raise ConjuntoInvalido(
                    f"AccessDenied leyendo s3://{self._bucket}/{key}: ¿la policy del bucket permite este vpce?"
                ) from e
            raise
