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

    def como_mensaje(self) -> dict[str, Any]:
        """El cuerpo que recibe el worker: por HTTP en /inferir o como mensaje de SQS."""
        return {
            "trabajo_id": str(self.trabajo_id),
            "modelo": {"nombre": self.modelo_nombre, "version": self.modelo_version,
                       "bucket": self.modelo_bucket, "prefix": self.modelo_prefix},
            "estudio": {"bucket": self.estudio_bucket, "key": self.estudio_key},
        }


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


class TrabajosSinEnviar(Protocol):
    """Modo sqs: la usa solo el reenviador."""
    def tomar_para_reenviar(self, minutos: int, limite: int) -> list[Trabajo]: ...  # pendientes viejos; toca `actualizado`
    def vencer_en_curso(self, minutos: int, motivo: str) -> int: ...                # en_curso sin noticias → error


# ---- almacenamiento -----------------------------------------------------------------

class AlmacenEstudios(Protocol):
    def firmar_subida(self, key: str, content_type: str, max_bytes: int) -> SubidaFirmada: ...
    def describir(self, key: str) -> ObjetoAlmacenado: ...          # NoEncontrado si no se subió


class CatalogoModelosEnBucket(Protocol):
    """El bucket de modelos. Los casos de uso hablan de prefijos; qué archivos
    hay adentro de cada uno lo sabe el adaptador."""
    def listar(self) -> list[RefModeloEnBucket]: ...                # prefijos con modelo.json
    def leer_contrato(self, prefix: str) -> dict[str, Any]: ...     # NoEncontrado
    def existe(self, prefix: str) -> bool: ...                      # el prefijo ya está ocupado
    def firmar_subida(self, prefix: str, max_bytes: int) -> SubidaFirmada: ...   # el ONNX
    def describir_modelo(self, prefix: str) -> ObjetoAlmacenado: ...             # NoEncontrado
    def escribir_contrato(self, prefix: str, contrato: dict[str, Any]) -> None: ...


# ---- servicios ----------------------------------------------------------------------

class ClienteInferencia(Protocol):
    def inferir(self, p: PeticionInferencia) -> ResultadoInferencia: ...  # ServicioNoDisponible | FalloDefinitivo


class ColaInferencias(Protocol):
    """Modo sqs: deja el pedido para que lo tome algún worker."""
    def enviar(self, p: PeticionInferencia) -> None: ...                  # ServicioNoDisponible


class Reloj(Protocol):
    def ahora(self) -> datetime: ...
