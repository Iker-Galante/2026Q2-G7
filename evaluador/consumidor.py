"""El evaluador tira de la cola `evaluaciones`.

Un mensaje por vez: es una sola tarea a propósito (una certificación es una medición atribuible
a una máquina). Una evaluación de cientos de casos puede pasar la visibilidad de la cola, así
que un latido la renueva mientras dura; si la tarea muere, el latido se corta y SQS vuelve a
entregar el mensaje.
"""

from __future__ import annotations

import json
import logging
import threading
from uuid import UUID

from .aplicacion import EvaluarModelo
from .puertos import ColaEvaluaciones, Mensaje, ModeloPendiente

log = logging.getLogger(__name__)


class MensajeInvalido(Exception):
    pass


def modelo_de(cuerpo: str) -> ModeloPendiente:
    try:
        d = json.loads(cuerpo)
        if d.get("tipo") != "evaluar_modelo":
            raise MensajeInvalido(f"tipo desconocido: {d.get('tipo')!r}")
        return ModeloPendiente(id=UUID(d["modelo_id"]), nombre=d["nombre"], version=d["version"],
                               tipo_estudio=d["tipo_estudio"], s3_prefix=d["prefix"], etiquetas=list(d["etiquetas"]))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise MensajeInvalido(f"{e.__class__.__name__}: {e}") from e


class Latido:
    """Mientras dura el `with`, renueva la invisibilidad del mensaje cada `cada_s` segundos."""

    def __init__(self, cola: ColaEvaluaciones, m: Mensaje, cada_s: int, visibilidad_s: int):
        self._cola, self._m = cola, m
        self._cada, self._visibilidad = cada_s, visibilidad_s
        self._fin = threading.Event()
        self._hilo = threading.Thread(target=self._latir, name="latido", daemon=True)

    def _latir(self) -> None:
        while not self._fin.wait(self._cada):
            try:
                self._cola.extender(self._m, self._visibilidad)
            except Exception:                                     # noqa: BLE001
                log.exception("no se pudo extender la visibilidad del mensaje")

    def __enter__(self) -> "Latido":
        self._hilo.start()
        return self

    def __exit__(self, *_) -> None:
        self._fin.set()
        self._hilo.join(timeout=5)


class ConsumidorEvaluaciones:
    def __init__(self, cola: ColaEvaluaciones, evaluar: EvaluarModelo, espera_s: int,
                 latido_s: int, visibilidad_s: int):
        self._cola = cola
        self._evaluar = evaluar
        self._espera_s = espera_s
        self._latido_s = latido_s
        self._visibilidad_s = visibilidad_s

    def una_vuelta(self) -> bool:
        """Toma y procesa un mensaje. False si la cola estaba vacía."""
        m = self._cola.recibir(self._espera_s)
        if m is None:
            return False
        try:
            modelo = modelo_de(m.cuerpo)
        except MensajeInvalido as e:
            log.error("mensaje ilegible, se descarta: %s · %r", e, m.cuerpo[:200])
            self._cola.borrar(m)
            return True
        with Latido(self._cola, m, self._latido_s, self._visibilidad_s):
            self._evaluar.ejecutar(modelo)
        self._cola.borrar(m)
        return True

    def correr(self, detener: threading.Event) -> None:
        log.info("consumidor de evaluaciones arrancado")
        while not detener.is_set():
            try:
                self.una_vuelta()
            except Exception:                                      # noqa: BLE001 — el bucle no puede morir
                log.exception("error en el consumidor; sigo")
                detener.wait(5)
        log.info("consumidor de evaluaciones detenido")
