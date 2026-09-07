"""El sitio estático, servido por el propio backend (no hay CloudFront en el lab).

Se monta AL FINAL: lo que se monta en "/" atrapa todo lo que no matcheó antes.
Un 404 fuera de /api devuelve index.html, para las rutas del lado del cliente.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


def montar(app: FastAPI, web_dir: str) -> None:
    carpeta = Path(web_dir)
    indice = carpeta / "index.html"
    if not indice.is_file():
        log.warning("sin sitio estático: no existe %s (en desarrollo usá `npm run dev`)", indice)
        return

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, e: StarletteHTTPException):
        if e.status_code == 404 and not request.url.path.startswith("/api"):
            return FileResponse(indice)
        return JSONResponse(status_code=e.status_code, content={"error": "http", "detalle": str(e.detail)})

    app.mount("/", StaticFiles(directory=carpeta, html=True), name="web")
    log.info("sitio estático montado desde %s", carpeta)
