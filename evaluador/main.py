"""Ateneo · evaluador (eval-1, subred aislada).

`python -m evaluador.main`
Bucle: tomar un modelo pendiente de la base → evaluarlo contra el conjunto reservado → escribir.
A esta instancia no se entra: todo lo que pasa queda en este log y en la fila del modelo.
"""

from __future__ import annotations

import logging
import os
import socket
import time
import urllib.request

import boto3
from botocore.config import Config as BotoConfig

from .aplicacion import EvaluarModelo
from .config import Settings
from .infraestructura.cola_postgres import ColaPostgres
from .infraestructura.conjunto_s3 import ConjuntoS3
from .infraestructura.modelo_s3 import ModeloS3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.evaluador")


def identidad() -> str:
    """El instance id por IMDSv2 (la NACL no lo filtra); si no hay metadatos, el hostname."""
    try:
        pedido = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        token = urllib.request.urlopen(pedido, timeout=1).read().decode()
        pedido = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id",
                                        headers={"X-aws-ec2-metadata-token": token})
        return urllib.request.urlopen(pedido, timeout=1).read().decode()
    except Exception:  # noqa: BLE001
        return socket.gethostname()


def main() -> None:
    cfg = Settings.desde_entorno()
    yo = identidad()
    s3 = boto3.client("s3", region_name=cfg.aws_region,
                      config=BotoConfig(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3},
                                        s3={"addressing_style": "path" if os.environ.get("AWS_ENDPOINT_URL") else "auto"}))
    cola = ColaPostgres(cfg.database_url, yo)
    evaluar = EvaluarModelo(cola, ConjuntoS3(s3, cfg.bucket_evaluacion), ModeloS3(s3, cfg.bucket_modelos),
                            cfg.directorio_trabajo, cfg.max_fraccion_errores, cfg.hilos)

    while True:
        try:
            reencolados = cola.reencolar_en_curso()
            if reencolados:
                log.warning("reencolados %s modelos que quedaron en_curso", reencolados)
            break
        except Exception as e:  # noqa: BLE001 — la base puede tardar en estar disponible
            log.warning("sin base todavía (%s); reintento en %ss", e, cfg.intervalo_segundos)
            time.sleep(cfg.intervalo_segundos)

    log.info("evaluador listo · yo=%s · evaluacion=%s · modelos=%s", yo, cfg.bucket_evaluacion, cfg.bucket_modelos)
    while True:
        try:
            modelo = cola.tomar_pendiente()
        except Exception as e:  # noqa: BLE001
            log.warning("no pude consultar la base: %s", e)
            modelo = None
        if modelo is None:
            time.sleep(cfg.intervalo_segundos)
            continue
        evaluar.ejecutar(modelo)


if __name__ == "__main__":
    main()
