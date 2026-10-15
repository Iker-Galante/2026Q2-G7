from __future__ import annotations

import socket
import time

from .puertos import FuenteImagenes, ProveedorModelos, RefModelo, RefObjeto, Resultado

__all__ = ["Inferir", "Resultado"]


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
