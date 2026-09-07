"""decodificar → preprocesar → inferir → posprocesar, en un solo objeto."""

from __future__ import annotations

from .contrato import ContratoModelo
from .decodificadores import decodificador_para
from .motor import Motor
from .postprocesamiento import Prediccion, posprocesar
from .preprocesamiento import preprocesar


class Inferidor:
    def __init__(self, contrato: ContratoModelo, motor: Motor):
        self.contrato = contrato
        self._motor = motor

    def inferir(self, datos: bytes, nombre_archivo: str) -> Prediccion:
        imagen = decodificador_para(nombre_archivo).decodificar(datos)
        tensor = preprocesar(imagen, self.contrato.entrada)
        salida = self._motor.inferir(tensor)
        return posprocesar(salida, self.contrato.salida)
