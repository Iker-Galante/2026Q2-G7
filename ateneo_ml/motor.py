"""El motor que ejecuta el grafo. Hoy solo ONNX Runtime."""

from __future__ import annotations

import logging
import os
from typing import Protocol

import numpy as np

from .contrato import ContratoModelo
from .errores import ModeloIncompatible

log = logging.getLogger(__name__)


class Motor(Protocol):
    def inferir(self, tensor: np.ndarray) -> np.ndarray: ...


class OnnxMotor:
    """Carga una sesión de ONNX Runtime validada contra el contrato."""

    def __init__(self, ruta_onnx: str, contrato: ContratoModelo, hilos: int | None = None):
        import onnxruntime as ort  # import tardío: el backend no lo tiene

        opciones = ort.SessionOptions()
        opciones.intra_op_num_threads = hilos or os.cpu_count() or 1
        opciones.log_severity_level = 3
        self._sesion = ort.InferenceSession(ruta_onnx, opciones, providers=["CPUExecutionProvider"])
        self._entrada = _resolver_nombre(
            contrato.entrada.nombre, [i.name for i in self._sesion.get_inputs()], "entrada"
        )
        self._salida = _resolver_nombre(
            contrato.salida.nombre, [o.name for o in self._sesion.get_outputs()], "salida"
        )
        _validar_forma(self._sesion, self._entrada, contrato)

    def inferir(self, tensor: np.ndarray) -> np.ndarray:
        (salida,) = self._sesion.run([self._salida], {self._entrada: tensor})
        return np.asarray(salida, dtype=np.float32)


def _resolver_nombre(declarado: str | None, disponibles: list[str], que: str) -> str:
    if declarado is None:
        if len(disponibles) != 1:
            raise ModeloIncompatible(
                f"el contrato no declara {que}.nombre y el grafo tiene {len(disponibles)}: {disponibles}"
            )
        return disponibles[0]
    if declarado in disponibles:
        return declarado
    if len(disponibles) == 1:
        log.warning("el contrato declara %s '%s' pero el grafo solo tiene '%s'; se usa esa",
                    que, declarado, disponibles[0])
        return disponibles[0]
    raise ModeloIncompatible(f"{que} '{declarado}' no existe en el grafo; hay {disponibles}")


def _validar_forma(sesion, nombre_entrada: str, contrato: ContratoModelo) -> None:
    entrada = next(i for i in sesion.get_inputs() if i.name == nombre_entrada)
    declarada = contrato.entrada.forma
    real = entrada.shape
    if len(real) != len(declarada):
        raise ModeloIncompatible(f"la entrada del grafo tiene forma {real} y el contrato declara {declarada}")
    for r, d in zip(real, declarada):
        if isinstance(r, int) and r != d and r != 1:
            raise ModeloIncompatible(f"la entrada del grafo tiene forma {real} y el contrato declara {declarada}")
