from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ateneo_ml import Inferidor


@dataclass(frozen=True)
class RefModelo:
    nombre: str
    version: str
    bucket: str
    prefix: str


@dataclass(frozen=True)
class RefObjeto:
    bucket: str
    key: str


class ProveedorModelos(Protocol):
    def obtener(self, ref: RefModelo) -> Inferidor: ...       # NoEncontrado | ModeloIncompatible


class FuenteImagenes(Protocol):
    def leer(self, ref: RefObjeto) -> bytes: ...               # NoEncontrado


class NoEncontrado(Exception):
    pass


# ---- modo sqs -----------------------------------------------------------------------

@dataclass(frozen=True)
class Mensaje:
    cuerpo: str              # el mismo JSON que recibe POST /inferir
    recibo: str              # para borrarlo o devolverlo a la cola
    recepciones: int         # ApproximateReceiveCount: 1 la primera vez


class ColaInferencias(Protocol):
    def recibir(self, espera_s: int) -> Mensaje | None: ...
    def borrar(self, m: Mensaje) -> None: ...
    def devolver(self, m: Mensaje, en_s: int) -> None: ...   # visible de nuevo en en_s segundos


class ResultadosTrabajos(Protocol):
    """Lo único que el worker escribe en la base: el estado de su trabajo. Todo idempotente:
    SQS entrega al menos una vez, así que el mismo trabajo puede llegar dos veces."""
    def tomar(self, trabajo_id: str, worker: str) -> bool: ...      # False si ya terminó o no existe
    def terminar_ok(self, trabajo_id: str, worker: str, prediccion: str,
                    probabilidades: dict[str, float], duracion_ms: int) -> None: ...
    def terminar_error(self, trabajo_id: str, motivo: str) -> None: ...
    def reintentar(self, trabajo_id: str, motivo: str) -> None: ...  # vuelve a pendiente
