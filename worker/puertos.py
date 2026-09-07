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
