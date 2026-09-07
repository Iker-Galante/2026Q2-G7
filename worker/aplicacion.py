from __future__ import annotations

import socket
import time
from dataclasses import dataclass

from .puertos import FuenteImagenes, ProveedorModelos, RefModelo, RefObjeto


@dataclass(frozen=True)
class Resultado:
    prediccion: str
    probabilidades: dict[str, float]
    duracion_ms: int
    worker: str


class Inferir:
    """Una inferencia: bajar la imagen, correr el modelo, devolver. Sin estado, sin base."""

    def __init__(self, modelos: ProveedorModelos, imagenes: FuenteImagenes):
        self._modelos = modelos
        self._imagenes = imagenes
        self._yo = socket.gethostname()

    def ejecutar(self, modelo: RefModelo, estudio: RefObjeto) -> Resultado:
        inicio = time.perf_counter()
        inferidor = self._modelos.obtener(modelo)
        datos = self._imagenes.leer(estudio)
        prediccion = inferidor.inferir(datos, estudio.key)
        return Resultado(
            prediccion=prediccion.prediccion,
            probabilidades=prediccion.probabilidades,
            duracion_ms=int((time.perf_counter() - inicio) * 1000),
            worker=self._yo,
        )
