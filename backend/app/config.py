"""Configuración del backend. Todo viene del entorno (/etc/ateneo.env en EC2)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str
    aws_region: str = "us-east-1"
    bucket_modelos: str
    bucket_estudios: str
    inferencia_url: str                      # http://internal-alb-...:8081
    origen_web: str | None = None            # informativo; sitio y API comparten origen

    web_dir: str = "/opt/ateneo/web"         # de dónde se sirve el sitio estático
    timeout_inferencia_s: float = 30.0
    max_intentos: int = 3
    intervalo_despacho_s: float = 1.0
    huerfanos_minutos: int = 2               # en_curso sin actualizar → vuelve a pendiente
    max_bytes_estudio: int = 20 * 1024 * 1024
    max_bytes_modelo: int = 512 * 1024 * 1024
    despachador_activo: bool = True          # False para tests o para separar roles

    # Solo desarrollo local: host público de MinIO para las URLs prefirmadas
    # (el backend habla con http://minio:9000 pero el navegador ve http://localhost:9000).
    s3_url_publica: str | None = None

    prefijo_modelos: str = "modelos/"
    prefijo_estudios: str = "estudios/"
