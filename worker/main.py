"""Ateneo · worker de inferencia (capa inferencia, puerto 8081).

`uvicorn worker.main:app --host 0.0.0.0 --port 8081`
Sin estado y sin base: recibe referencias a S3, devuelve la predicción.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import boto3
from botocore.config import Config as BotoConfig
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ateneo_ml import ContratoInvalido
from ateneo_ml.errores import ImagenIlegible, ModeloIncompatible

from .aplicacion import Inferir
from .config import Settings
from .consumidor import Consumidor, ProcesarMensaje
from .infraestructura.fuente_s3 import FuenteS3
from .infraestructura.proveedor_efs_s3 import ProveedorEfsS3
from .puertos import NoEncontrado, RefModelo, RefObjeto

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logging.getLogger("botocore").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.worker")


class ModeloPeticion(BaseModel):
    nombre: str
    version: str
    bucket: str
    prefix: str


class EstudioPeticion(BaseModel):
    bucket: str
    key: str


class InferirPeticion(BaseModel):
    trabajo_id: str
    modelo: ModeloPeticion
    estudio: EstudioPeticion


class InferirRespuesta(BaseModel):
    trabajo_id: str
    worker: str
    prediccion: str
    probabilidades: dict[str, float]
    duracion_ms: int


def crear_app() -> FastAPI:
    settings = Settings.desde_entorno()
    settings.validar()
    s3 = boto3.client("s3", region_name=settings.aws_region,
                      config=BotoConfig(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2},
                                        s3={"addressing_style": "path" if os.environ.get("AWS_ENDPOINT_URL") else "auto"}))
    inferir = Inferir(
        ProveedorEfsS3(s3, settings.modelos_dir, settings.cache_sesiones, settings.hilos),
        FuenteS3(s3),
    )

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        consumidor = None
        if settings.modo_inferencia == "sqs":
            from .infraestructura.cola_sqs import ColaSqs
            from .infraestructura.trabajos_postgres import ResultadosPostgres

            sqs = boto3.client("sqs", region_name=settings.aws_region,
                               config=BotoConfig(connect_timeout=5, read_timeout=settings.espera_s + 10,
                                                 retries={"max_attempts": 3}))
            cola = ColaSqs(sqs, settings.cola_inferencias_url)
            procesar = ProcesarMensaje(inferir, cola, ResultadosPostgres(settings.database_url),
                                       settings.max_intentos, settings.reintento_s)
            consumidor = Consumidor(cola, procesar, settings.espera_s)
            consumidor.arrancar()
        try:
            yield
        finally:
            if consumidor is not None:
                consumidor.detener()

    app = FastAPI(title="Ateneo worker", docs_url=None, redoc_url=None, lifespan=ciclo_de_vida)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/inferir", response_model=InferirRespuesta)
    def ruta_inferir(p: InferirPeticion) -> InferirRespuesta:
        r = inferir.ejecutar(
            RefModelo(p.modelo.nombre, p.modelo.version, p.modelo.bucket, p.modelo.prefix),
            RefObjeto(p.estudio.bucket, p.estudio.key),
        )
        log.info("inferido trabajo_id=%s modelo=%s prediccion=%s ms=%s",
                 p.trabajo_id, p.modelo.nombre, r.prediccion, r.duracion_ms)
        return InferirRespuesta(trabajo_id=p.trabajo_id, worker=r.worker, prediccion=r.prediccion,
                                probabilidades=r.probabilidades, duracion_ms=r.duracion_ms)

    # Errores: 4xx = no reintentar (el backend los marca definitivos); 5xx = reintentar.
    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, e: NoEncontrado):
        return JSONResponse(404, {"error": "no_encontrado", "detalle": str(e)})

    @app.exception_handler(ImagenIlegible)
    async def _ilegible(_: Request, e: ImagenIlegible):
        return JSONResponse(400, {"error": "imagen_ilegible", "detalle": str(e)})

    @app.exception_handler(ModeloIncompatible)
    async def _incompatible(_: Request, e: ModeloIncompatible):
        return JSONResponse(400, {"error": "modelo_incompatible", "detalle": str(e)})

    @app.exception_handler(ContratoInvalido)
    async def _contrato(_: Request, e: ContratoInvalido):
        return JSONResponse(400, {"error": "contrato_invalido", "detalle": str(e)})

    log.info("worker listo · modo=%s · modelos_dir=%s", settings.modo_inferencia, settings.modelos_dir)
    return app


app = crear_app()
