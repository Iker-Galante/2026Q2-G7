"""Esquemas HTTP (pydantic). Se convierten desde el dominio acá y en ningún otro lado."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from ..aplicacion.casos_uso.estudios import EstudioCreado
from ..aplicacion.casos_uso.modelos import ModeloDisponible, SubidaModelo
from ..dominio.modelo import Modelo
from ..dominio.trabajo import Trabajo


class ErrorRespuesta(BaseModel):
    error: str
    detalle: str


class SubidaRespuesta(BaseModel):
    """POST prefirmado de S3: los campos van antes del archivo, en ese orden."""
    url: str
    campos: dict[str, str]


class ModeloDisponibleRespuesta(BaseModel):
    nombre: str
    version: str
    tipo_estudio: str
    publicado: bool
    modelo_id: UUID | None

    @staticmethod
    def desde(m: ModeloDisponible) -> "ModeloDisponibleRespuesta":
        return ModeloDisponibleRespuesta(**m.__dict__)


# Los dos segmentos del prefijo en S3: sin barras ni espacios.
NombreModelo = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")]
VersionModelo = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")]


class PrepararSubidaModeloPeticion(BaseModel):
    nombre: NombreModelo
    version: VersionModelo
    tamano_bytes: int = Field(gt=0)


class PublicarModeloPeticion(BaseModel):
    nombre: NombreModelo
    version: VersionModelo
    # Presente cuando el modelo se acaba de subir desde la interfaz: la API lo
    # valida y lo escribe como modelo.json al lado del ONNX. Ausente cuando el
    # modelo ya estaba en el bucket con su contrato.
    contrato: dict[str, Any] | None = None


class SubidaModeloRespuesta(BaseModel):
    prefix: str
    subida: SubidaRespuesta

    @staticmethod
    def desde(c: SubidaModelo) -> "SubidaModeloRespuesta":
        return SubidaModeloRespuesta(
            prefix=c.prefix, subida=SubidaRespuesta(url=c.subida.url, campos=c.subida.campos),
        )


class ModeloRespuesta(BaseModel):
    id: UUID
    nombre: str
    version: str
    tipo_estudio: str
    tarea: str
    etiquetas: list[str]
    estado_evaluacion: str
    accuracy: float | None
    metricas: dict[str, Any] | None
    conjunto: str | None
    conjunto_version: str | None
    manifiesto: dict[str, Any] | None
    evaluador_id: str | None
    evaluado_en: datetime | None
    error: str | None
    creado: datetime
    publicado: datetime
    nombre_visible: str | None = None
    predeterminado: bool = False

    @staticmethod
    def desde(m: Modelo) -> "ModeloRespuesta":
        from tools.demo_assets import catalogo
        inicial = next((md for md in catalogo() if (md.nombre, md.version) == (m.nombre, m.version)), None)
        return ModeloRespuesta(
            id=m.id, nombre=m.nombre, version=m.version, tipo_estudio=m.tipo_estudio, tarea=m.tarea,
            etiquetas=m.etiquetas, estado_evaluacion=m.estado_evaluacion, accuracy=m.accuracy,
            metricas=m.metricas, conjunto=m.conjunto, conjunto_version=m.conjunto_version,
            manifiesto=m.manifiesto, evaluador_id=m.evaluador_id, evaluado_en=m.evaluado_en,
            error=m.error, creado=m.creado, publicado=m.publicado,
            nombre_visible=inicial.nombre_visible if inicial else None,
            predeterminado=inicial is not None,
        )


class CrearEstudioPeticion(BaseModel):
    tipo_estudio: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9-]+$")
    nombre_archivo: str = Field(min_length=1, max_length=255)
    content_type: str
    tamano_bytes: int = Field(gt=0)


class EstudioCreadoRespuesta(BaseModel):
    estudio_id: UUID
    s3_key: str
    subida: SubidaRespuesta

    @staticmethod
    def desde(c: EstudioCreado) -> "EstudioCreadoRespuesta":
        return EstudioCreadoRespuesta(
            estudio_id=c.estudio.id, s3_key=c.estudio.s3_key,
            subida=SubidaRespuesta(url=c.subida.url, campos=c.subida.campos),
        )


class EncolarInferenciaPeticion(BaseModel):
    estudio_id: UUID
    modelo_id: UUID


class ResultadoRespuesta(BaseModel):
    prediccion: str
    probabilidades: dict[str, float]


class TrabajoRespuesta(BaseModel):
    id: UUID
    estudio_id: UUID
    modelo_id: UUID
    estado: str
    intentos: int
    worker_id: str | None
    duracion_ms: int | None
    resultado: ResultadoRespuesta | None
    error: str | None
    creado: datetime
    actualizado: datetime

    @staticmethod
    def desde(t: Trabajo) -> "TrabajoRespuesta":
        return TrabajoRespuesta(
            id=t.id, estudio_id=t.estudio_id, modelo_id=t.modelo_id, estado=t.estado, intentos=t.intentos,
            worker_id=t.worker_id, duracion_ms=t.duracion_ms,
            resultado=ResultadoRespuesta(**t.resultado) if t.resultado else None,
            error=t.error, creado=t.creado, actualizado=t.actualizado,
        )
