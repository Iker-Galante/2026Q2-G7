"""Configuración del worker. Solo `os.environ`: la imagen dorada no trae pydantic-settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_region: str = "us-east-1"
    modelos_dir: str = "/mnt/modelos"        # EFS en AWS; una carpeta local en desarrollo
    cache_sesiones: int = 4                  # cuántos modelos cargados se mantienen en memoria
    hilos: int | None = None                 # None = todos los vCPU

    @staticmethod
    def desde_entorno() -> "Settings":
        e = os.environ
        return Settings(
            aws_region=e.get("AWS_REGION", "us-east-1"),
            modelos_dir=e.get("MODELOS_DIR", "/mnt/modelos"),
            cache_sesiones=int(e.get("CACHE_SESIONES", "4")),
            hilos=int(e["HILOS"]) if e.get("HILOS") else None,
        )
