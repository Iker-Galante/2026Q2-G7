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

    # Modo sqs: además de /inferir, un hilo consume la cola y escribe el resultado en la base.
    modo_inferencia: str = "http"
    cola_inferencias_url: str | None = None
    database_url: str | None = None
    max_intentos: int = 3                    # igual al maxReceiveCount de la cola (Terraform)
    espera_s: int = 20                       # long polling
    reintento_s: int = 10                    # un fallo transitorio vuelve a la cola en este tiempo

    @staticmethod
    def desde_entorno() -> "Settings":
        e = os.environ
        return Settings(
            aws_region=e.get("AWS_REGION", "us-east-1"),
            modelos_dir=e.get("MODELOS_DIR", "/mnt/modelos"),
            cache_sesiones=int(e.get("CACHE_SESIONES", "4")),
            hilos=int(e["HILOS"]) if e.get("HILOS") else None,
            modo_inferencia=e.get("MODO_INFERENCIA", "http"),
            cola_inferencias_url=e.get("COLA_INFERENCIAS_URL") or None,
            database_url=e.get("DATABASE_URL") or None,
            max_intentos=int(e.get("MAX_INTENTOS", "3")),
            espera_s=int(e.get("ESPERA_COLA_S", "20")),
            reintento_s=int(e.get("REINTENTO_S", "10")),
        )

    def validar(self) -> None:
        if self.modo_inferencia == "sqs":
            faltan = [n for n, v in (("COLA_INFERENCIAS_URL", self.cola_inferencias_url),
                                     ("DATABASE_URL", self.database_url)) if not v]
            if faltan:
                raise SystemExit(f"modo sqs: faltan variables de entorno: {', '.join(faltan)}")
