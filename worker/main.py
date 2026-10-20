"""Ateneo · worker de inferencia (servicio `worker` de ECS, capa de inferencia).

`python -m worker.main`
Sin puertos de entrada, sin base y sin internet: lee de la cola `inferencias` (por el endpoint
de SQS), baja modelo y estudio de S3 (por el endpoint Gateway), y publica en `resultados`.
"""

from __future__ import annotations

import logging
import os
import signal
import threading

import boto3
from botocore.config import Config as BotoConfig

from .aplicacion import Inferir
from .config import Settings
from .consumidor import Consumidor, ProcesarMensaje
from .infraestructura.cola_sqs import ColaSqs, ResultadosSqs
from .infraestructura.fuente_s3 import FuenteS3
from .infraestructura.proveedor_efs_s3 import ProveedorEfsS3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.worker")


def main() -> None:
    settings = Settings.desde_entorno()
    local = os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("AWS_ENDPOINT_URL")
    s3 = boto3.client("s3", region_name=settings.aws_region,
                      config=BotoConfig(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2},
                                        s3={"addressing_style": "path" if local else "auto"}))
    sqs = boto3.client("sqs", region_name=settings.aws_region,
                       config=BotoConfig(connect_timeout=5, read_timeout=settings.espera_s + 10,
                                         retries={"max_attempts": 3}))

    inferir = Inferir(ProveedorEfsS3(s3, settings.modelos_dir, settings.cache_sesiones, settings.hilos), FuenteS3(s3))
    cola = ColaSqs(sqs, settings.cola_inferencias_url)
    procesar = ProcesarMensaje(inferir, cola, ResultadosSqs(sqs, settings.cola_resultados_url),
                               settings.max_intentos, settings.reintento_s)

    detener = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())

    log.info("worker listo · inferencias=%s · modelos_dir=%s", settings.cola_inferencias_url, settings.modelos_dir)
    Consumidor(cola, procesar, settings.espera_s).correr(detener)


if __name__ == "__main__":
    main()
