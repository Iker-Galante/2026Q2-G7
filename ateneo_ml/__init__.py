"""Código compartido entre el worker de inferencia y el evaluador.

Solo depende de numpy, pillow y onnxruntime: es lo que trae la imagen dorada.
La garantía que da este paquete es que la accuracy que escribe el evaluador se
mide con exactamente el mismo preprocesamiento, motor y posprocesamiento que
usa el worker cuando atiende a un usuario.
"""

from .contrato import ContratoModelo, ContratoInvalido, EspecEntrada, EspecSalida
from .pipeline import Inferidor, Prediccion

__all__ = [
    "ContratoModelo",
    "ContratoInvalido",
    "EspecEntrada",
    "EspecSalida",
    "Inferidor",
    "Prediccion",
]
