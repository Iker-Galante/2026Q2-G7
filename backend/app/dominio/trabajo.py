from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from .estudio import Estudio
from .modelo import Modelo

ESTADOS = ("pendiente", "en_curso", "ok", "error")


@dataclass(frozen=True)
class ResultadoInferencia:
    prediccion: str
    probabilidades: dict[str, float]
    worker_id: str
    duracion_ms: int

    def como_dict(self) -> dict[str, Any]:
        return {"prediccion": self.prediccion, "probabilidades": self.probabilidades}


@dataclass
class Trabajo:
    id: UUID
    estudio_id: UUID
    modelo_id: UUID
    estado: str
    intentos: int
    creado: datetime
    actualizado: datetime
    worker_id: str | None = None
    resultado: dict[str, Any] | None = None
    duracion_ms: int | None = None
    error: str | None = None

    @staticmethod
    def nuevo(estudio: Estudio, modelo: Modelo, ahora: datetime) -> "Trabajo":
        return Trabajo(
            id=uuid4(),
            estudio_id=estudio.id,
            modelo_id=modelo.id,
            estado="pendiente",
            intentos=0,
            creado=ahora,
            actualizado=ahora,
        )

    def marcar_ok(self, r: ResultadoInferencia, ahora: datetime) -> None:
        self.estado = "ok"
        self.resultado = r.como_dict()
        self.worker_id = r.worker_id
        self.duracion_ms = r.duracion_ms
        self.error = None
        self.actualizado = ahora

    def marcar_fallido(self, motivo: str, ahora: datetime, max_intentos: int, definitivo: bool = False) -> None:
        """Vuelve a `pendiente` para reintentar, o pasa a `error` si se agotaron los intentos.

        `intentos` ya fue incrementado al tomar el trabajo de la cola.
        """
        self.actualizado = ahora
        if definitivo or self.intentos >= max_intentos:
            self.estado = "error"
            self.error = motivo if definitivo else f"{motivo} (tras {self.intentos} intentos)"
        else:
            self.estado = "pendiente"
            self.error = motivo
