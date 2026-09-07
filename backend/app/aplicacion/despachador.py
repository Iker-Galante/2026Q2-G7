"""El despachador: la "cola" hecha código.

Un bucle por proceso del backend. Toma trabajos `pendiente` de la tabla con
`SKIP LOCKED` (varios procesos e instancias compiten sin pisarse), los lleva al
ALB interno y guarda el resultado. Cada tanto devuelve a `pendiente` los que
quedaron `en_curso` porque murió el proceso que los tenía.
"""

from __future__ import annotations

import asyncio
import logging

from .casos_uso.inferencias import DespacharTrabajo
from .puertos import ColaTrabajos

log = logging.getLogger(__name__)


class Despachador:
    def __init__(self, cola: ColaTrabajos, despachar: DespacharTrabajo, intervalo_s: float,
                 max_intentos: int, huerfanos_minutos: int, barrido_huerfanos_s: float = 60.0):
        self._cola = cola
        self._despachar = despachar
        self._intervalo = intervalo_s
        self._max_intentos = max_intentos
        self._huerfanos_minutos = huerfanos_minutos
        self._barrido_s = barrido_huerfanos_s

    async def correr(self, detener: asyncio.Event) -> None:
        log.info("despachador arrancado intervalo=%ss", self._intervalo)
        desde_ultimo_barrido = self._barrido_s   # barrer apenas arranca
        while not detener.is_set():
            try:
                if desde_ultimo_barrido >= self._barrido_s:
                    n = await asyncio.to_thread(self._cola.reencolar_huerfanos, self._huerfanos_minutos)
                    if n:
                        log.warning("reencolados %s trabajos huérfanos", n)
                    desde_ultimo_barrido = 0.0

                trabajo = await asyncio.to_thread(self._cola.tomar_pendiente, self._max_intentos)
                if trabajo is not None:
                    await asyncio.to_thread(self._despachar.ejecutar, trabajo)
                    continue                                      # hay cola: no dormir
            except Exception:                                     # noqa: BLE001 — el bucle no puede morir
                log.exception("error en el despachador; sigo")
            try:
                await asyncio.wait_for(detener.wait(), timeout=self._intervalo)
            except asyncio.TimeoutError:
                pass
            desde_ultimo_barrido += self._intervalo
        log.info("despachador detenido")
