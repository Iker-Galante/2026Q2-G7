"""El worker tira de la cola `inferencias` y publica en `resultados`. No abre ningún puerto.

Por cada mensaje: avisar que empezó, inferir, publicar el resultado y recién entonces
borrar el mensaje. Si el worker muere a mitad, el mensaje no se borró y SQS lo vuelve a
entregar al vencer la visibilidad: no hay huérfanos que barrer.

  - error definitivo (imagen ilegible, modelo incompatible, objeto inexistente) → publica
    el error y borra: reintentarlo daría lo mismo.
  - error transitorio → el mensaje vuelve a la cola en pocos segundos. En la recepción
    número `max_intentos` publica el error y lo deja: SQS lo pasa a la cola de fallidos y
    la alarma avisa por SNS.
"""

from __future__ import annotations

import json
import logging
import socket
import threading

from ateneo_ml import ContratoInvalido
from ateneo_ml.errores import ImagenIlegible, ModeloIncompatible

from .aplicacion import Inferir
from .puertos import ColaInferencias, Mensaje, NoEncontrado, RefModelo, RefObjeto, ResultadosInferencia

log = logging.getLogger(__name__)

DEFINITIVOS = (NoEncontrado, ImagenIlegible, ModeloIncompatible, ContratoInvalido)


class ProcesarMensaje:
    def __init__(self, inferir: Inferir, cola: ColaInferencias, resultados: ResultadosInferencia,
                 max_intentos: int, reintento_s: int):
        self._inferir = inferir
        self._cola = cola
        self._resultados = resultados
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

        self._resultados.en_curso(trabajo_id, self._yo, m.recepciones)
        try:
            r = self._inferir.ejecutar(modelo, estudio)
        except DEFINITIVOS as e:
            self._resultados.error(trabajo_id, f"{e.__class__.__name__}: {e}")
            self._cola.borrar(m)
            log.warning("trabajo rechazado trabajo_id=%s motivo=%s", trabajo_id, e)
            return
        except Exception as e:                                     # noqa: BLE001 — transitorio hasta que se demuestre lo contrario
            motivo = f"{e.__class__.__name__}: {e}"
            if m.recepciones >= self._max_intentos:
                # Se deja el mensaje: en la próxima entrega SQS lo pasa a la cola de fallidos.
                self._resultados.error(trabajo_id, f"{motivo} (tras {m.recepciones} intentos)")
                log.error("trabajo agotado trabajo_id=%s intento=%s motivo=%s", trabajo_id, m.recepciones, motivo)
            else:
                self._cola.devolver(m, self._reintento_s)
                log.warning("trabajo fallido trabajo_id=%s intento=%s motivo=%s", trabajo_id, m.recepciones, motivo)
            return

        self._resultados.ok(trabajo_id, r)
        self._cola.borrar(m)
        log.info("inferido trabajo_id=%s prediccion=%s ms=%s", trabajo_id, r.prediccion, r.duracion_ms)


class Consumidor:
    """El bucle. Corre hasta que llega SIGTERM (ECS lo manda al reemplazar o achicar el servicio):
    termina el mensaje que tiene entre manos y sale."""

    def __init__(self, cola: ColaInferencias, procesar: ProcesarMensaje, espera_s: int):
        self._cola = cola
        self._procesar = procesar
        self._espera_s = espera_s

    def correr(self, detener: threading.Event) -> None:
        log.info("consumidor arrancado")
        while not detener.is_set():
            try:
                m = self._cola.recibir(self._espera_s)
                if m is not None:
                    self._procesar.ejecutar(m)
            except Exception:                                      # noqa: BLE001 — el bucle no puede morir
                log.exception("error en el consumidor; sigo")
                detener.wait(5)
        log.info("consumidor detenido")
