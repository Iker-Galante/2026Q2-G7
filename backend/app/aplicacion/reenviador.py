"""El reenviador: lo que queda del despachador cuando la cola es SQS.

Ya no lleva trabajos al worker (los workers tiran de la cola) ni rescata huérfanos (SQS
devuelve solo el mensaje de un worker que murió). Solo corre, cada tanto, `ReenviarPendientes`.
"""

from __future__ import annotations

import asyncio
import logging

from .casos_uso.inferencias import ReenviarPendientes

log = logging.getLogger(__name__)


class Reenviador:
    def __init__(self, reenviar: ReenviarPendientes, intervalo_s: float = 60.0):
        self._reenviar = reenviar
        self._intervalo = intervalo_s

    async def correr(self, detener: asyncio.Event) -> None:
        log.info("reenviador arrancado intervalo=%ss", self._intervalo)
        while not detener.is_set():
            try:
                await asyncio.to_thread(self._reenviar.ejecutar)
            except Exception:                                     # noqa: BLE001 — el bucle no puede morir
                log.exception("error en el reenviador; sigo")
            try:
                await asyncio.wait_for(detener.wait(), timeout=self._intervalo)
            except asyncio.TimeoutError:
                pass
        log.info("reenviador detenido")
