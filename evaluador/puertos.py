from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Protocol
from uuid import UUID


@dataclass
class ModeloPendiente:
    id: UUID
    nombre: str
    version: str
    tipo_estudio: str
    s3_prefix: str
    etiquetas: list[str]


@dataclass(frozen=True)
class Caso:
    nombre: str
    etiqueta: str


@dataclass(frozen=True)
class Conjunto:
    tipo_estudio: str
    version: str
    manifiesto: dict[str, Any]
    casos: list[Caso]


@dataclass(frozen=True)
class ResultadoEvaluacion:
    metricas: dict[str, Any]
    conjunto: str
    conjunto_version: str
    manifiesto: dict[str, Any]
    terminado: datetime


class ResultadosEvaluacion(Protocol):
    """La cola `resultados`. El evaluador no tiene credenciales de base: publica, y el
    procesador escribe. Solo salen métricas agregadas, nunca el resultado caso por caso."""
    def en_curso(self, modelo: ModeloPendiente) -> None: ...
    def terminar_ok(self, modelo: ModeloPendiente, r: ResultadoEvaluacion) -> None: ...
    def terminar_error(self, modelo: ModeloPendiente, motivo: str) -> None: ...


@dataclass(frozen=True)
class Mensaje:
    cuerpo: str
    recibo: str


class ColaEvaluaciones(Protocol):
    def recibir(self, espera_s: int) -> Mensaje | None: ...
    def borrar(self, m: Mensaje) -> None: ...
    def extender(self, m: Mensaje, segundos: int) -> None: ...   # sigue invisible mientras se evalúa


class LectorConjunto(Protocol):
    def ultima_version(self, tipo_estudio: str) -> str | None: ...
    def cargar(self, tipo_estudio: str, version: str) -> Conjunto: ...
    def leer_caso(self, conjunto: Conjunto, caso: Caso) -> bytes: ...
    def listar_casos(self, tipo_estudio: str, version: str) -> Iterator[str]: ...


class DescargadorModelo(Protocol):
    def descargar(self, s3_prefix: str, destino: Path) -> Path: ...   # carpeta con modelo.onnx y modelo.json


class ConjuntoInvalido(Exception):
    pass
