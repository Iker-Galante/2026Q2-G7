"""Configuración del evaluador. Solo `os.environ`: la imagen dorada no trae pydantic-settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    bucket_evaluacion: str
    bucket_modelos: str
    aws_region: str = "us-east-1"
    intervalo_segundos: float = 10.0
    directorio_trabajo: str = "/opt/worker/tmp"
    max_fraccion_errores: float = 0.05        # más de esto y la evaluación termina en error
    hilos: int | None = None

    @staticmethod
    def desde_entorno() -> "Settings":
        e = os.environ
        faltan = [v for v in ("DATABASE_URL", "BUCKET_EVALUACION", "BUCKET_MODELOS") if not e.get(v)]
        if faltan:
            raise SystemExit(f"faltan variables de entorno: {', '.join(faltan)}")
        return Settings(
            database_url=e["DATABASE_URL"],
            bucket_evaluacion=e["BUCKET_EVALUACION"],
            bucket_modelos=e["BUCKET_MODELOS"],
            aws_region=e.get("AWS_REGION", "us-east-1"),
            intervalo_segundos=float(e.get("INTERVALO_SEGUNDOS", "10")),
            directorio_trabajo=e.get("DIRECTORIO_TRABAJO", "/opt/worker/tmp"),
            max_fraccion_errores=float(e.get("MAX_FRACCION_ERRORES", "0.05")),
            hilos=int(e["HILOS"]) if e.get("HILOS") else None,
        )
