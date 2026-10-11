"""Modo sqs: el worker tira de la cola en vez de esperar al ALB interno.

Por cada mensaje: tomar el trabajo en la base, inferir, guardar el resultado y recién
entonces borrar el mensaje. Si el worker muere a mitad, el mensaje no se borró y SQS lo
vuelve a entregar al vencer la visibilidad: no hay huérfanos que barrer.

  - error definitivo (imagen ilegible, modelo incompatible, objeto inexistente) → `error`
    y se borra: reintentarlo daría lo mismo.
  - error transitorio → vuelve a `pendiente` y el mensaje se devuelve a la cola en pocos
    segundos. En la recepción número `max_intentos` se marca `error` y se deja: SQS lo pasa
    a la DLQ y la alarma avisa por SNS.
"""

from __future__ import annotations

import json
import logging
import socket
import threading

from ateneo_ml import ContratoInvalido
from ateneo_ml.errores import ImagenIlegible, ModeloIncompatible

from .aplicacion import Inferir
from .puertos import ColaInferencias, Mensaje, NoEncontrado, RefModelo, RefObjeto, ResultadosTrabajos

log = logging.getLogger(__name__)

DEFINITIVOS = (NoEncontrado, ImagenIlegible, ModeloIncompatible, ContratoInvalido)


class ProcesarMensaje:
    def __init__(self, inferir: Inferir, cola: ColaInferencias, trabajos: ResultadosTrabajos,
                 max_intentos: int, reintento_s: int):
        self._inferir = inferir
        self._cola = cola
        self._trabajos = trabajos
        self._max_intentos = max_intentos
        self._reintento_s = reintento_s
        self._yo = socket.gethostname()

    def ejecutar(self, m: Mensaje) -> None:
        try:
            p = json.loads(m.cuerpo)
            trabajo_id = p["trabajo_id"]
            modelo = RefModelo(p["modelo"]["nombre"], p["modelo"]["version"], p["modelo"]["bucket"], p["modelo"]["prefix"])
            estudio = RefObjeto(p["estudio"]["bucket"], p["estudio"]["key"])
        except (ValueError, KeyError, TypeError) as e:
            log.error("mensaje ilegible, se descarta: %s · %r", e, m.cuerpo[:200])
            self._cola.borrar(m)
            return

        if not self._trabajos.tomar(trabajo_id, self._yo):
            log.info("trabajo_id=%s ya terminado o inexistente; mensaje repetido, se descarta", trabajo_id)
            self._cola.borrar(m)
            return

        try:
            r = self._inferir.ejecutar(modelo, estudio)
        except DEFINITIVOS as e:
            self._trabajos.terminar_error(trabajo_id, f"{e.__class__.__name__}: {e}")
            self._cola.borrar(m)
            log.warning("trabajo rechazado trabajo_id=%s motivo=%s", trabajo_id, e)
            return
        except Exception as e:                                     # noqa: BLE001 — transitorio hasta que se demuestre lo contrario
            motivo = f"{e.__class__.__name__}: {e}"
            if m.recepciones >= self._max_intentos:
                # Se deja el mensaje: en la próxima entrega SQS lo pasa a la DLQ.
                self._trabajos.terminar_error(trabajo_id, f"{motivo} (tras {m.recepciones} intentos)")
                log.error("trabajo agotado trabajo_id=%s intento=%s motivo=%s", trabajo_id, m.recepciones, motivo)
            else:
                self._trabajos.reintentar(trabajo_id, motivo)
                self._cola.devolver(m, self._reintento_s)
                log.warning("trabajo fallido trabajo_id=%s intento=%s motivo=%s", trabajo_id, m.recepciones, motivo)
            return

        self._trabajos.terminar_ok(trabajo_id, r.worker, r.prediccion, r.probabilidades, r.duracion_ms)
        self._cola.borrar(m)
        log.info("inferido trabajo_id=%s prediccion=%s ms=%s", trabajo_id, r.prediccion, r.duracion_ms)


class Consumidor:
    """El bucle, en un hilo propio: boto3 y onnxruntime bloquean, y /health tiene que seguir contestando."""

    def __init__(self, cola: ColaInferencias, procesar: ProcesarMensaje, espera_s: int):
        self._cola = cola
        self._procesar = procesar
        self._espera_s = espera_s
        self._detener = threading.Event()
        self._hilo = threading.Thread(target=self._correr, name="consumidor-sqs", daemon=True)

    def arrancar(self) -> None:
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()
        self._hilo.join(timeout=self._espera_s + 5)

    def _correr(self) -> None:
        log.info("consumidor arrancado")
        while not self._detener.is_set():
            try:
                m = self._cola.recibir(self._espera_s)
                if m is not None:
                    self._procesar.ejecutar(m)
            except Exception:                                      # noqa: BLE001 — el bucle no puede morir
                log.exception("error en el consumidor; sigo")
                self._detener.wait(5)
        log.info("consumidor detenido")
