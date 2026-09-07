from fastapi import APIRouter, Depends, status

from ...aplicacion.casos_uso.estudios import CrearEstudio
from ..dependencias import dep_crear_estudio, usuario_actual
from ..esquemas import CrearEstudioPeticion, ErrorRespuesta, EstudioCreadoRespuesta

router = APIRouter(prefix="/api/estudios", tags=["estudios"], dependencies=[Depends(usuario_actual)])


@router.post(
    "",
    response_model=EstudioCreadoRespuesta,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorRespuesta}},
)
def crear(peticion: CrearEstudioPeticion, caso: CrearEstudio = Depends(dep_crear_estudio)):
    return EstudioCreadoRespuesta.desde(
        caso.ejecutar(peticion.tipo_estudio, peticion.content_type, peticion.tamano_bytes)
    )
