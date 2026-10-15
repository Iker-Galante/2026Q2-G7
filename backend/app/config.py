"""Configuración del backend. Todo viene del entorno (/etc/ateneo.env en EC2)."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: str
    aws_region: str = "us-east-1"
    bucket_modelos: str
    bucket_estudios: str
    # "http": el despachador lleva cada trabajo al ALB interno (INFERENCIA_URL).
    # "sqs":  el backend encola en SQS (COLA_INFERENCIAS_URL) y los workers consumen.
    modo_inferencia: Literal["http", "sqs"] = "http"
    inferencia_url: str | None = None        # http://internal-alb-...:8081
    cola_inferencias_url: str | None = None  # https://sqs.us-east-1.amazonaws.com/<cuenta>/ateneo-inferencias
    origen_web: str | None = None            # informativo: el sitio (en AWS, el bucket web)
    # Con los dos, cada pedido a /api/* tiene que traer un access token válido de ese user pool.
    # Sin ellos (docker compose, tests) todos son anónimos.
    cognito_user_pool_id: str | None = None  # us-east-1_XXXXXXXXX
    cognito_client_id: str | None = None

    web_dir: str = "/opt/ateneo/web"         # de dónde se sirve el sitio estático
    timeout_inferencia_s: float = 30.0
    max_intentos: int = 3
    intervalo_despacho_s: float = 1.0
    huerfanos_minutos: int = 2               # en_curso sin actualizar → vuelve a pendiente
    max_bytes_estudio: int = 20 * 1024 * 1024
    max_bytes_modelo: int = 512 * 1024 * 1024
    despachador_activo: bool = True          # False para tests o para separar roles (en sqs: el reenviador)
    reenvio_minutos: int = 5                 # sqs: pendiente sin tomar → se vuelve a encolar
    vencimiento_en_curso_minutos: int = 10   # sqs: en_curso sin noticias → error

    # Solo desarrollo local: host público de MinIO para las URLs prefirmadas
    # (el backend habla con http://minio:9000 pero el navegador ve http://localhost:9000).
    s3_url_publica: str | None = None

    prefijo_modelos: str = "modelos/"
    prefijo_estudios: str = "estudios/"

    @model_validator(mode="after")
    def _modo_completo(self) -> "Settings":
        if self.modo_inferencia == "http" and not self.inferencia_url:
            raise ValueError("modo http: falta INFERENCIA_URL")
        if self.modo_inferencia == "sqs" and not self.cola_inferencias_url:
            raise ValueError("modo sqs: falta COLA_INFERENCIAS_URL")
        if bool(self.cognito_user_pool_id) != bool(self.cognito_client_id):
            raise ValueError("Cognito: hacen falta COGNITO_USER_POOL_ID y COGNITO_CLIENT_ID, o ninguno")
        return self
