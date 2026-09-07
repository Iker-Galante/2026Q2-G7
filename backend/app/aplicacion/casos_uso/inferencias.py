from __future__ import annotations

import logging
from uuid import UUID

from ...dominio.errores import Conflicto, FalloDefinitivo, NoEncontrado, ServicioNoDisponible
from ...dominio.trabajo import Trabajo
from ..puertos import (
    AlmacenEstudios, ClienteInferencia, PeticionInferencia, Reloj,
    RepositorioEstudios, RepositorioModelos, RepositorioTrabajos,
)

log = logging.getLogger(__name__)


class EncolarInferencia:
    """Confirma la subida, valida compatibilidad e inserta el trabajo en `pendiente`.

    No llama al worker: de eso se encarga el despachador.
    """

    def __init__(self, estudios: RepositorioEstudios, modelos: RepositorioModelos,
                 trabajos: RepositorioTrabajos, almacen: AlmacenEstudios, reloj: Reloj):
        self._estudios = estudios
        self._modelos = modelos
        self._trabajos = trabajos
        self._almacen = almacen
        self._reloj = reloj

    def ejecutar(self, estudio_id: UUID, modelo_id: UUID) -> Trabajo:
        estudio = self._estudios.obtener(estudio_id)
        modelo = self._modelos.obtener(modelo_id)
        if estudio.estado != "subido":
            try:
                estudio.confirmar(self._almacen.describir(estudio.s3_key))
            except NoEncontrado:
                raise Conflicto("el archivo del estudio todavía no está en S3; subilo antes de inferir") from None
            self._estudios.guardar(estudio)
        modelo.verificar_compatible(estudio)
        trabajo = Trabajo.nuevo(estudio, modelo, self._reloj.ahora())
        self._trabajos.guardar(trabajo)
        log.info("trabajo encolado trabajo_id=%s modelo=%s estudio=%s", trabajo.id, modelo.nombre, estudio.id)
        return trabajo


class ConsultarTrabajo:
    def __init__(self, trabajos: RepositorioTrabajos):
        self._trabajos = trabajos

    def ejecutar(self, id: UUID) -> Trabajo:
        return self._trabajos.obtener(id)


class DespacharTrabajo:
    """Lleva un trabajo (ya en `en_curso`) al worker y guarda lo que pasó."""

    def __init__(self, estudios: RepositorioEstudios, modelos: RepositorioModelos,
                 trabajos: RepositorioTrabajos, cliente: ClienteInferencia, reloj: Reloj,
                 bucket_modelos: str, bucket_estudios: str, max_intentos: int):
        self._estudios = estudios
        self._modelos = modelos
        self._trabajos = trabajos
        self._cliente = cliente
        self._reloj = reloj
        self._bucket_modelos = bucket_modelos
        self._bucket_estudios = bucket_estudios
        self._max_intentos = max_intentos

    def ejecutar(self, trabajo: Trabajo) -> None:
        modelo = self._modelos.obtener(trabajo.modelo_id)
        estudio = self._estudios.obtener(trabajo.estudio_id)
        peticion = PeticionInferencia(
            trabajo_id=trabajo.id,
            modelo_nombre=modelo.nombre, modelo_version=modelo.version,
            modelo_bucket=self._bucket_modelos, modelo_prefix=modelo.s3_prefix,
            estudio_bucket=self._bucket_estudios, estudio_key=estudio.s3_key,
        )
        try:
            resultado = self._cliente.inferir(peticion)
            trabajo.marcar_ok(resultado, self._reloj.ahora())
            log.info("trabajo ok trabajo_id=%s worker=%s ms=%s", trabajo.id, resultado.worker_id, resultado.duracion_ms)
        except ServicioNoDisponible as e:
            trabajo.marcar_fallido(str(e), self._reloj.ahora(), self._max_intentos)
            log.warning("trabajo fallido trabajo_id=%s intento=%s estado=%s motivo=%s",
                        trabajo.id, trabajo.intentos, trabajo.estado, e)
        except FalloDefinitivo as e:
            trabajo.marcar_fallido(str(e), self._reloj.ahora(), self._max_intentos, definitivo=True)
            log.warning("trabajo rechazado trabajo_id=%s motivo=%s", trabajo.id, e)
        self._trabajos.guardar(trabajo)
