"""Configuración del evaluador. Solo `os.environ`: la imagen ml no trae pydantic-settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cola_evaluaciones_url: str
    cola_resultados_url: str
    bucket_evaluacion: str
    bucket_modelos: str
    aws_region: str = "us-east-1"
    espera_s: int = 20                        # long polling
    visibilidad_s: int = 1800                 # igual al visibility_timeout de la cola (Terraform)
    latido_s: int = 300                       # cada cuánto se renueva mientras evalúa
    directorio_trabajo: str = "/opt/ml/tmp"
    max_fraccion_errores: float = 0.05        # más de esto y la evaluación termina en error
    hilos: int | None = None

    @staticmethod
    def desde_entorno() -> "Settings":
        e = os.environ
        requeridas = ("COLA_EVALUACIONES_URL", "COLA_RESULTADOS_URL", "BUCKET_EVALUACION", "BUCKET_MODELOS")
        faltan = [v for v in requeridas if not e.get(v)]
        if faltan:
            raise SystemExit(f"faltan variables de entorno: {', '.join(faltan)}")
        return Settings(
            cola_evaluaciones_url=e["COLA_EVALUACIONES_URL"],
            cola_resultados_url=e["COLA_RESULTADOS_URL"],
            bucket_evaluacion=e["BUCKET_EVALUACION"],
            bucket_modelos=e["BUCKET_MODELOS"],
            aws_region=e.get("AWS_REGION", "us-east-1"),
            espera_s=int(e.get("ESPERA_COLA_S", "20")),
            visibilidad_s=int(e.get("VISIBILIDAD_S", "1800")),
            latido_s=int(e.get("LATIDO_S", "300")),
            directorio_trabajo=e.get("DIRECTORIO_TRABAJO", "/opt/ml/tmp"),
            max_fraccion_errores=float(e.get("MAX_FRACCION_ERRORES", "0.05")),
            hilos=int(e["HILOS"]) if e.get("HILOS") else None,
        )
