"""Ateneo · backend (capa app).

`uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2`
Cada proceso arma su propio contenedor, su pool y su despachador.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import dependencias, errores, sitio
from .api.rutas import estudios, inferencias, modelos, salud
from .config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s · %(message)s",
)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("ateneo.backend")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    settings = Settings()
    contenedor = dependencias.armar(settings)
    contenedor.abrir()
    app.state.contenedor = contenedor

    detener = asyncio.Event()
    tarea = None
    if settings.despachador_activo:
        tarea = asyncio.create_task(contenedor.despachador.correr(detener), name="despachador")
    log.info("backend listo · inferencia=%s · modelos=%s · estudios=%s",
             settings.inferencia_url, settings.bucket_modelos, settings.bucket_estudios)
    try:
        yield
    finally:
        detener.set()
        if tarea is not None:
            await tarea
        contenedor.cerrar()
        log.info("backend detenido")


def crear_app() -> FastAPI:
    app = FastAPI(title="Ateneo", version="0.1.0", lifespan=ciclo_de_vida,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    errores.registrar(app)
    app.include_router(salud.router)
    app.include_router(modelos.router)
    app.include_router(estudios.router)
    app.include_router(inferencias.router)
    sitio.montar(app, os.environ.get("WEB_DIR", "/opt/ateneo/web"))   # siempre al final
    return app


app = crear_app()
