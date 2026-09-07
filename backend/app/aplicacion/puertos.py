"""Puertos: lo que la aplicación necesita del mundo exterior, sin decir cómo.

Los adaptadores en `infraestructura/` los implementan. Los tests los reemplazan
por fakes en memoria. Nadie más los importa que los casos de uso y los adaptadores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from ..dominio.estudio import Estudio, ObjetoAlmacenado
from ..dominio.modelo import Modelo
from ..dominio.trabajo import ResultadoInferencia, Trabajo


# ---- valores que cruzan los puertos -------------------------------------------------

@dataclass(frozen=True)
class SubidaFirmada:
    url: str
    campos: dict[str, str]


@dataclass(frozen=True)
class RefModeloEnBucket:
    nombre: str
    version: str
    prefix: str            # modelos/<nombre>/<version>/


@dataclass(frozen=True)
class PeticionInferencia:
    trabajo_id: UUID
    modelo_nombre: str
    modelo_version: str
    modelo_bucket: str
    modelo_prefix: str
    estudio_bucket: str
    estudio_key: str


# ---- repositorios -------------------------------------------------------------------

class RepositorioModelos(Protocol):
    def guardar(self, m: Modelo) -> None: ...
    def obtener(self, id: UUID) -> Modelo: ...                      # NoEncontrado
    def buscar(self, nombre: str, version: str) -> Modelo | None: ...
    def listar(self) -> list[Modelo]: ...


class RepositorioEstudios(Protocol):
    def guardar(self, e: Estudio) -> None: ...
    def obtener(self, id: UUID) -> Estudio: ...                     # NoEncontrado


class RepositorioTrabajos(Protocol):
    def guardar(self, t: Trabajo) -> None: ...
    def obtener(self, id: UUID) -> Trabajo: ...                     # NoEncontrado


class ColaTrabajos(Protocol):
    """La usa solo el despachador."""
    def tomar_pendiente(self, max_intentos: int) -> Trabajo | None: ...   # atómico: pendiente → en_curso, intentos + 1
    def reencolar_huerfanos(self, minutos: int) -> int: ...


# ---- almacenamiento -----------------------------------------------------------------

class AlmacenEstudios(Protocol):
    def firmar_subida(self, key: str, content_type: str, max_bytes: int) -> SubidaFirmada: ...
    def describir(self, key: str) -> ObjetoAlmacenado: ...          # NoEncontrado si no se subió


class CatalogoModelosEnBucket(Protocol):
    def listar(self) -> list[RefModeloEnBucket]: ...                # prefijos con modelo.json
    def leer_contrato(self, prefix: str) -> dict[str, Any]: ...    # NoEncontrado


# ---- servicios ----------------------------------------------------------------------

class ClienteInferencia(Protocol):
    def inferir(self, p: PeticionInferencia) -> ResultadoInferencia: ...  # ServicioNoDisponible | FalloDefinitivo


class Reloj(Protocol):
    def ahora(self) -> datetime: ...
