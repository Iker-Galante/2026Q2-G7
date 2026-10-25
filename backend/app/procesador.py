"""Ateneo · procesador (servicio `procesador` de ECS, capa de aplicación, sin puertos de entrada).

`python -m app.procesador`
Es el único proceso que escribe resultados en la base (decisión 04 de la arquitectura):
  1. al arrancar aplica las migraciones que falten, con un candado de la base para que dos
     tareas no lo hagan a la vez;
  2. consume la cola `resultados`, donde publican el worker y el evaluador;
  3. cada minuto vuelve a encolar las inferencias que quedaron pendientes sin mensaje y vence
     lo que quedó en curso sin noticias (un worker o el evaluador murieron en el último intento).

Usa la misma imagen que la API: la de `backend`.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
import time
from pathlib import Path

from .aplicacion.casos_uso.inferencias import ReenviarPendientes
from .aplicacion.casos_uso.modelos import VencerEvaluaciones
from .aplicacion.casos_uso.resultados import AplicarResultado, MensajeInvalido
from .config import Settings
from .infraestructura.aws import cliente_s3, cliente_sqs
from .infraestructura.postgres import migraciones
from .infraestructura.postgres.conexion import crear_pool
from .infraestructura.postgres.repositorios import (
    RegistroResultadosPostgres, RepositorioEstudiosPostgres, RepositorioModelosPostgres,
    RepositorioTrabajosPostgres,
)
from .infraestructura.sqs.colas import ColaSqs, MensajeRecibido

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.procesador")

ESPERA_S = 20          # long polling


def migrar(settings: Settings, detener: threading.Event) -> None:
    """La base puede tardar en estar lista (primer arranque, o RDS saliendo de un reinicio)."""
    while not detener.is_set():
        try:
            nuevas = migraciones.aplicar(settings.database_url, Path(settings.migraciones_dir))
            log.info("migraciones al día%s", f" · aplicadas: {', '.join(nuevas)}" if nuevas else "")
            return
        except Exception as e:                                    # noqa: BLE001
            log.warning("no se pudieron aplicar las migraciones (%s); reintento en 10 s", e)
            detener.wait(10)


def reenviar_cada(intervalo_s: float, tareas: list, detener: threading.Event) -> None:
    while not detener.wait(intervalo_s):
        for tarea in tareas:
            try:
                tarea.ejecutar()
            except Exception:                                     # noqa: BLE001 — el bucle no puede morir
                log.exception("error en %s; sigo", tarea.__class__.__name__)


def procesar(m: MensajeRecibido, aplicar: AplicarResultado, cola: ColaSqs) -> None:
    try:
        cambio = aplicar.ejecutar(json.loads(m.cuerpo))
        log.info("resultado %s: %s", "aplicado" if cambio else "repetido, sin cambios", m.cuerpo[:160])
    except (MensajeInvalido, ValueError) as e:
        log.error("mensaje inválido, se descarta: %s · %r", e, m.cuerpo[:200])
    # Si la base falló, la excepción sale de acá y el mensaje no se borra: SQS lo vuelve a
    # entregar y, después de 5 intentos, lo pasa a la cola de fallidos.
    cola.borrar(m)


def main() -> None:
    settings = Settings()
    settings.exigir("cola_resultados_url")

    detener = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: detener.set())     # ECS manda SIGTERM al reemplazar la tarea

    migrar(settings, detener)

    pool = crear_pool(settings.database_url)
    pool.open()
    sqs = cliente_sqs(settings.aws_region, ESPERA_S)
    resultados = ColaSqs(sqs, settings.cola_resultados_url)
    aplicar = AplicarResultado(RegistroResultadosPostgres(pool))

    modelos = RepositorioModelosPostgres(pool)
    trabajos = RepositorioTrabajosPostgres(pool)
    tareas = [
        ReenviarPendientes(trabajos, RepositorioEstudiosPostgres(pool), modelos,
                           ColaSqs(sqs, settings.cola_inferencias_url),
                           settings.bucket_modelos, settings.bucket_estudios,
                           settings.reenvio_minutos, settings.vencimiento_en_curso_minutos),
        VencerEvaluaciones(modelos, settings.vencimiento_evaluacion_minutos),
    ]
    if settings.datos_demo:
        from .demo import InicializarDemo
        settings.exigir("cola_evaluaciones_url")
        tareas.append(InicializarDemo(pool, cliente_s3(settings.aws_region), sqs, settings))
    reenviador = threading.Thread(target=reenviar_cada, args=(settings.intervalo_reenvio_s, tareas, detener),
                                  name="reenviador", daemon=True)
    reenviador.start()

    log.info("procesador listo · resultados=%s", settings.cola_resultados_url)
    while not detener.is_set():
        try:
            for m in resultados.recibir(ESPERA_S):
                procesar(m, aplicar, resultados)
        except Exception:                                         # noqa: BLE001
            log.exception("error procesando resultados; sigo en 5 s")
            time.sleep(5)

    reenviador.join(timeout=5)
    pool.close()
    log.info("procesador detenido")


if __name__ == "__main__":
    main()
