from uuid import UUID

from fastapi import APIRouter, Depends, status

from ...aplicacion.casos_uso.modelos import (
    ConsultarModelo, ListarModelos, ListarModelosDisponibles, PrepararSubidaModelo, PublicarModelo,
)
from ..dependencias import (
    dep_consultar_modelo, dep_listar_disponibles, dep_listar_modelos, dep_preparar_subida,
    dep_publicar_modelo, usuario_actual,
)
from ..esquemas import (
    ErrorRespuesta, ModeloDisponibleRespuesta, ModeloRespuesta, PrepararSubidaModeloPeticion,
    PublicarModeloPeticion, SubidaModeloRespuesta,
)

router = APIRouter(prefix="/api/modelos", tags=["modelos"], dependencies=[Depends(usuario_actual)])


@router.get("/disponibles", response_model=list[ModeloDisponibleRespuesta])
def disponibles(caso: ListarModelosDisponibles = Depends(dep_listar_disponibles)):
    return [ModeloDisponibleRespuesta.desde(m) for m in caso.ejecutar()]


@router.post(
    "/subidas",
    response_model=SubidaModeloRespuesta,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorRespuesta}, 422: {"model": ErrorRespuesta}},
)
def preparar_subida(peticion: PrepararSubidaModeloPeticion,
                    caso: PrepararSubidaModelo = Depends(dep_preparar_subida)):
    """Firma la subida del ONNX. El navegador lo manda directo al bucket."""
    return SubidaModeloRespuesta.desde(caso.ejecutar(peticion.nombre, peticion.version, peticion.tamano_bytes))


@router.post(
    "/publicar",
    response_model=ModeloRespuesta,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorRespuesta}, 409: {"model": ErrorRespuesta}, 422: {"model": ErrorRespuesta}},
)
def publicar(peticion: PublicarModeloPeticion, caso: PublicarModelo = Depends(dep_publicar_modelo)):
    return ModeloRespuesta.desde(caso.ejecutar(peticion.nombre, peticion.version, peticion.contrato))


@router.get("", response_model=list[ModeloRespuesta])
def listar(caso: ListarModelos = Depends(dep_listar_modelos)):
    return [ModeloRespuesta.desde(m) for m in caso.ejecutar()]


@router.get("/{modelo_id}", response_model=ModeloRespuesta, responses={404: {"model": ErrorRespuesta}})
def obtener(modelo_id: UUID, caso: ConsultarModelo = Depends(dep_consultar_modelo)):
    return ModeloRespuesta.desde(caso.ejecutar(modelo_id))
