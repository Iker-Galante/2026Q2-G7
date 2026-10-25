"""Configuración del worker. Solo `os.environ`: la imagen ml no trae pydantic-settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    cola_inferencias_url: str
    cola_resultados_url: str
    aws_region: str = "us-east-1"
    modelos_dir: str = "/mnt/modelos"        # EFS en AWS; una carpeta local en desarrollo
    cache_sesiones: int = 4                  # cuántos modelos cargados se mantienen en memoria
    hilos: int | None = None                 # None = todos los vCPU
    max_intentos: int = 3                    # igual al maxReceiveCount de la cola (Terraform)
    espera_s: int = 20                       # long polling
    reintento_s: int = 10                    # un fallo transitorio vuelve a la cola en este tiempo

    @staticmethod
    def desde_entorno() -> "Settings":
        e = os.environ
        faltan = [v for v in ("COLA_INFERENCIAS_URL", "COLA_RESULTADOS_URL") if not e.get(v)]
        if faltan:
            raise SystemExit(f"faltan variables de entorno: {', '.join(faltan)}")
        return Settings(
            cola_inferencias_url=e["COLA_INFERENCIAS_URL"],
            cola_resultados_url=e["COLA_RESULTADOS_URL"],
            aws_region=e.get("AWS_REGION", "us-east-1"),
            modelos_dir=e.get("MODELOS_DIR", "/mnt/modelos"),
            cache_sesiones=int(e.get("CACHE_SESIONES", "4")),
            hilos=int(e["HILOS"]) if e.get("HILOS") else None,
            max_intentos=int(e.get("MAX_INTENTOS", "3")),
            espera_s=int(e.get("ESPERA_COLA_S", "20")),
            reintento_s=int(e.get("REINTENTO_S", "10")),
        )
