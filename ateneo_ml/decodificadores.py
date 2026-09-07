"""bytes → PIL.Image, elegido por extensión.

Agregar un formato (DICOM) es agregar una clase y una entrada en REGISTRO.
"""

from __future__ import annotations

import io
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from .errores import ImagenIlegible


class DecodificadorImagen(Protocol):
    def decodificar(self, datos: bytes) -> Image.Image: ...


class DecodificadorPillow:
    def decodificar(self, datos: bytes) -> Image.Image:
        try:
            img = Image.open(io.BytesIO(datos))
            img.load()
            return img
        except (UnidentifiedImageError, OSError) as e:
            raise ImagenIlegible(f"no se pudo decodificar la imagen: {e}") from e


REGISTRO: dict[str, DecodificadorImagen] = {
    ".png": DecodificadorPillow(),
    ".jpg": DecodificadorPillow(),
    ".jpeg": DecodificadorPillow(),
    ".bmp": DecodificadorPillow(),
    ".webp": DecodificadorPillow(),
}


def decodificador_para(nombre: str) -> DecodificadorImagen:
    ext = "." + nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    try:
        return REGISTRO[ext]
    except KeyError:
        raise ImagenIlegible(f"formato no soportado: '{ext or nombre}'") from None
