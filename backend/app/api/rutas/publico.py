"""El catálogo público: lo único que se ve sin ingresar (el Visitante de la spec, sección 2).

Vive bajo /api/publico/ porque el autorizador de API Gateway exime ese prefijo y solo ese
(terraform/api.tf). Nada que cuelgue de acá puede pedir identidad ni devolver algo que dependa
de quién pregunta. Lo del publicador —qué hay en el bucket, firmar una subida, publicar— sigue
en /api/modelos, con token.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ...aplicacion.casos_uso.modelos import ConsultarModelo, ListarModelos
from ..dependencias import dep_consultar_modelo, dep_listar_modelos
from ..esquemas import ErrorRespuesta, ModeloRespuesta

router = APIRouter(prefix="/api/publico", tags=["publico"])


@router.get("/demo")
def demo(request: Request):
    from ...demo import estado_demo
    from ...infraestructura.aws import cliente_s3
    c = request.app.state.contenedor
    return estado_demo(c.settings, c.pool, cliente_s3(c.settings.aws_region))


@router.get("/modelos", response_model=list[ModeloRespuesta])
def catalogo(caso: ListarModelos = Depends(dep_listar_modelos)):
    """Los modelos publicados, del más nuevo al más viejo."""
    return [ModeloRespuesta.desde(m) for m in caso.ejecutar()]


@router.get("/modelos/{modelo_id}", response_model=ModeloRespuesta, responses={404: {"model": ErrorRespuesta}})
def ficha(modelo_id: UUID, caso: ConsultarModelo = Depends(dep_consultar_modelo)):
    return ModeloRespuesta.desde(caso.ejecutar(modelo_id))
