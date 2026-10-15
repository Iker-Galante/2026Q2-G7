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


@dataclass(frozen=True)
class Resultado:
    prediccion: str
    probabilidades: dict[str, float]
    duracion_ms: int
    worker: str


class ProveedorModelos(Protocol):
    def obtener(self, ref: RefModelo) -> Inferidor: ...       # NoEncontrado | ModeloIncompatible


class FuenteImagenes(Protocol):
    def leer(self, ref: RefObjeto) -> bytes: ...               # NoEncontrado


class NoEncontrado(Exception):
    pass


# ---- colas --------------------------------------------------------------------------

@dataclass(frozen=True)
class Mensaje:
    cuerpo: str              # el JSON que deja la API: trabajo_id, modelo y estudio
    recibo: str              # para borrarlo o devolverlo a la cola
    recepciones: int         # ApproximateReceiveCount: 1 la primera vez


class ColaInferencias(Protocol):
    def recibir(self, espera_s: int) -> Mensaje | None: ...
    def borrar(self, m: Mensaje) -> None: ...
    def devolver(self, m: Mensaje, en_s: int) -> None: ...   # visible de nuevo en en_s segundos


class ResultadosInferencia(Protocol):
    """La cola `resultados`. El worker no tiene base ni credenciales: publica, y el procesador
    escribe. SQS entrega al menos una vez, así que lo mismo puede llegar dos veces; el
    procesador lo aplica una sola."""
    def en_curso(self, trabajo_id: str, worker: str, intento: int) -> None: ...
    def ok(self, trabajo_id: str, r: Resultado) -> None: ...
    def error(self, trabajo_id: str, motivo: str) -> None: ...
