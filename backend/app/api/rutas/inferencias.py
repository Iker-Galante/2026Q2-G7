from uuid import UUID

from fastapi import APIRouter, Depends, status

from ...aplicacion.casos_uso.inferencias import ConsultarTrabajo, EncolarInferencia
from ..dependencias import dep_consultar_trabajo, dep_encolar_inferencia, usuario_actual
from ..esquemas import EncolarInferenciaPeticion, ErrorRespuesta, TrabajoRespuesta

router = APIRouter(prefix="/api", tags=["inferencias"], dependencies=[Depends(usuario_actual)])


@router.post(
    "/inferencias",
    response_model=TrabajoRespuesta,
    status_code=status.HTTP_202_ACCEPTED,
    responses={404: {"model": ErrorRespuesta}, 409: {"model": ErrorRespuesta}, 422: {"model": ErrorRespuesta}},
)
def encolar(peticion: EncolarInferenciaPeticion, caso: EncolarInferencia = Depends(dep_encolar_inferencia)):
    return TrabajoRespuesta.desde(caso.ejecutar(peticion.estudio_id, peticion.modelo_id))


@router.get("/trabajos/{trabajo_id}", response_model=TrabajoRespuesta, responses={404: {"model": ErrorRespuesta}})
def obtener(trabajo_id: UUID, caso: ConsultarTrabajo = Depends(dep_consultar_trabajo)):
    return TrabajoRespuesta.desde(caso.ejecutar(trabajo_id))
