"""Ateneo · evaluador (servicio `evaluador` de ECS, subred de evaluación aislada).

`python -m evaluador.main`
Pasa de 0 a 1 tarea según su cola: un mensaje en `evaluaciones` lo arranca y la cola vacía por
un rato lo apaga. Sin credenciales de base ni internet: lee el modelo y el conjunto reservado por
el endpoint de S3 y publica las métricas agregadas en `resultados`.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import threading
import urllib.request

import boto3
from botocore.config import Config as BotoConfig

from .aplicacion import EvaluarModelo
from .config import Settings
from .consumidor import ConsumidorEvaluaciones
from .infraestructura.colas_sqs import ColaEvaluacionesSqs, ResultadosSqs
from .infraestructura.conjunto_s3 import ConjuntoS3
from .infraestructura.modelo_s3 import ModeloS3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.evaluador")


def identidad() -> str:
    """El id de la tarea de ECS (el endpoint de metadatos de la tarea; la NACL no lo filtra).
    Fuera de ECS, el hostname."""
    uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if uri:
        try:
            tarea = json.load(urllib.request.urlopen(f"{uri}/task", timeout=2))
            return "tarea-" + tarea["TaskARN"].rsplit("/", 1)[-1]
        except Exception:  # noqa: BLE001
            pass
    return socket.gethostname()


def main() -> None:
    cfg = Settings.desde_entorno()
    yo = identidad()
    local = os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("AWS_ENDPOINT_URL")
    s3 = boto3.client("s3", region_name=cfg.aws_region,
                      config=BotoConfig(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3},
                                        s3={"addressing_style": "path" if local else "auto"}))
    sqs = boto3.client("sqs", region_name=cfg.aws_region,
                       config=BotoConfig(connect_timeout=5, read_timeout=cfg.espera_s + 10, retries={"max_attempts": 3}))

    evaluar = EvaluarModelo(ResultadosSqs(sqs, cfg.cola_resultados_url, yo), ConjuntoS3(s3, cfg.bucket_evaluacion),
                            ModeloS3(s3, cfg.bucket_modelos), cfg.directorio_trabajo, cfg.max_fraccion_errores, cfg.hilos)
    consumidor = ConsumidorEvaluaciones(ColaEvaluacionesSqs(sqs, cfg.cola_evaluaciones_url), evaluar,
                                        cfg.espera_s, cfg.latido_s, cfg.visibilidad_s)

    detener = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())

    log.info("evaluador listo · yo=%s · evaluacion=%s · modelos=%s", yo, cfg.bucket_evaluacion, cfg.bucket_modelos)
    consumidor.correr(detener)


if __name__ == "__main__":
    main()
