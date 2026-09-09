"""Fakes en memoria de los puertos. Cumplen el contrato, incluidos los errores (Liskov)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.aplicacion.puertos import PeticionInferencia, RefModeloEnBucket, SubidaFirmada
from app.dominio.errores import NoEncontrado, ServicioNoDisponible
from app.dominio.estudio import Estudio, ObjetoAlmacenado
from app.dominio.modelo import Modelo
from app.dominio.trabajo import ResultadoInferencia, Trabajo


class RelojFijo:
    def __init__(self):
        self.t = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

    def ahora(self) -> datetime:
        return self.t

    def avanzar(self, segundos: float) -> None:
        self.t += timedelta(seconds=segundos)


class RepoModelosMemoria:
    def __init__(self):
        self.datos: dict[UUID, Modelo] = {}

    def guardar(self, m: Modelo) -> None:
        self.datos[m.id] = m

    def obtener(self, id: UUID) -> Modelo:
        if id not in self.datos:
            raise NoEncontrado(f"no existe el modelo {id}")
        return self.datos[id]

    def buscar(self, nombre, version):
        return next((m for m in self.datos.values() if (m.nombre, m.version) == (nombre, version)), None)

    def listar(self):
        return sorted(self.datos.values(), key=lambda m: m.publicado, reverse=True)


class RepoEstudiosMemoria:
    def __init__(self):
        self.datos: dict[UUID, Estudio] = {}

    def guardar(self, e: Estudio) -> None:
        self.datos[e.id] = e

    def obtener(self, id: UUID) -> Estudio:
        if id not in self.datos:
            raise NoEncontrado(f"no existe el estudio {id}")
        return self.datos[id]


class RepoTrabajosMemoria:
    """Repositorio y cola, como el de Postgres."""

    def __init__(self):
        self.datos: dict[UUID, Trabajo] = {}

    def guardar(self, t: Trabajo) -> None:
        self.datos[t.id] = t

    def obtener(self, id: UUID) -> Trabajo:
        if id not in self.datos:
            raise NoEncontrado(f"no existe el trabajo {id}")
        return self.datos[id]

    def tomar_pendiente(self, max_intentos: int) -> Trabajo | None:
        candidatos = sorted((t for t in self.datos.values() if t.estado == "pendiente" and t.intentos < max_intentos),
                            key=lambda t: t.actualizado)
        if not candidatos:
            return None
        t = candidatos[0]
        t.estado, t.intentos = "en_curso", t.intentos + 1
        return t

    def reencolar_huerfanos(self, minutos: int) -> int:
        return 0


class AlmacenMemoria:
    def __init__(self):
        self.objetos: dict[str, int] = {}

    def firmar_subida(self, key, content_type, max_bytes) -> SubidaFirmada:
        return SubidaFirmada(url="http://s3.local/bucket", campos={"key": key, "Content-Type": content_type})

    def describir(self, key) -> ObjetoAlmacenado:
        if key not in self.objetos:
            raise NoEncontrado(key)
        return ObjetoAlmacenado(tamano_bytes=self.objetos[key], etag="etag")


class CatalogoMemoria:
    def __init__(self, contratos: dict[str, dict[str, Any]] | None = None,
                 onnx: set[str] | None = None):
        self.contratos = contratos or {}     # prefix → modelo.json
        self.onnx = onnx or set()            # prefijos que ya tienen su modelo.onnx
        self.firmadas: list[str] = []        # prefijos para los que se firmó una subida

    def listar(self):
        refs = []
        for prefix in self.contratos:
            _, nombre, version, _ = prefix.split("/")
            refs.append(RefModeloEnBucket(nombre, version, prefix))
        return refs

    def leer_contrato(self, prefix):
        if prefix not in self.contratos:
            raise NoEncontrado(prefix)
        return self.contratos[prefix]

    def existe(self, prefix) -> bool:
        return prefix in self.contratos or prefix in self.onnx

    def firmar_subida(self, prefix, max_bytes) -> SubidaFirmada:
        self.firmadas.append(prefix)
        return SubidaFirmada(url="http://s3.local/modelos",
                             campos={"key": f"{prefix}modelo.onnx", "Content-Type": "application/octet-stream"})

    def describir_modelo(self, prefix) -> ObjetoAlmacenado:
        if prefix not in self.onnx:
            raise NoEncontrado(f"{prefix}modelo.onnx")
        return ObjetoAlmacenado(tamano_bytes=16_000_000, etag="etag")

    def escribir_contrato(self, prefix, contrato) -> None:
        self.contratos[prefix] = contrato


class ClienteInferenciaFalso:
    def __init__(self, fallos_antes_de_responder: int = 0, error=ServicioNoDisponible("worker caído")):
        self.fallos = fallos_antes_de_responder
        self.error = error
        self.peticiones: list[PeticionInferencia] = []

    def inferir(self, p: PeticionInferencia) -> ResultadoInferencia:
        self.peticiones.append(p)
        if self.fallos > 0:
            self.fallos -= 1
            raise self.error
        return ResultadoInferencia("PNEUMONIA", {"NORMAL": 0.1, "PNEUMONIA": 0.9}, "worker-1", 120)
