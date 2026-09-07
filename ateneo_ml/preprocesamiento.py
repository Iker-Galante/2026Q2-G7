"""PIL.Image → tensor numpy según lo que declara el contrato.

Es la única función que convierte imágenes en tensores en todo Ateneo. Por eso
vive acá y no en el worker: el evaluador tiene que medir con el mismo código.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from .contrato import EspecEntrada


def preprocesar(img: Image.Image, e: EspecEntrada) -> np.ndarray:
    img = _convertir_color(img, e.espacio_color)
    img = _redimensionar(img, e.alto, e.ancho, e.redimension)

    x = np.asarray(img, dtype=np.float32)          # HxW o HxWxC
    if x.ndim == 2:
        x = x[:, :, None]                            # HxWx1
    x = x / e.escala
    if e.media is not None and e.desvio is not None:
        x = (x - np.asarray(e.media, dtype=np.float32)) / np.asarray(e.desvio, dtype=np.float32)

    if e.layout == "NCHW":
        x = np.transpose(x, (2, 0, 1))               # CxHxW
    return np.ascontiguousarray(x[None, ...], dtype=np.float32)


def _convertir_color(img: Image.Image, espacio: str) -> Image.Image:
    if espacio == "RGB":
        return img.convert("RGB")
    if espacio == "L":
        return img.convert("L")
    if espacio == "gris_replicado":
        # Luma ITU-R 601-2 (0.299 R + 0.587 G + 0.114 B) copiada a los 3 canales.
        return img.convert("L").convert("RGB")
    raise ValueError(f"espacio de color desconocido: {espacio}")


def _redimensionar(img: Image.Image, alto: int, ancho: int, modo: str) -> Image.Image:
    if modo == "estirar":
        return img.resize((ancho, alto), Image.Resampling.BILINEAR)
    if modo == "recortar_centro":
        # Escala el lado corto al tamaño pedido y recorta el centro.
        escala = max(ancho / img.width, alto / img.height)
        nuevo = (max(ancho, round(img.width * escala)), max(alto, round(img.height * escala)))
        img = img.resize(nuevo, Image.Resampling.BILINEAR)
        izq = (img.width - ancho) // 2
        arr = (img.height - alto) // 2
        return img.crop((izq, arr, izq + ancho, arr + alto))
    raise ValueError(f"modo de redimensión desconocido: {modo}")
