"""Salida cruda del grafo → probabilidades por etiqueta + predicción.

Un tipo de salida nuevo es una función más en REGISTRO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .contrato import EspecSalida
from .errores import ModeloIncompatible


@dataclass(frozen=True)
class Prediccion:
    prediccion: str
    probabilidades: dict[str, float]

    def probabilidad_de(self, etiqueta: str) -> float:
        return self.probabilidades[etiqueta]


def _softmax(v: np.ndarray) -> np.ndarray:
    v = v - v.max()
    e = np.exp(v)
    return e / e.sum()


def _desde_logits(salida: np.ndarray, s: EspecSalida) -> np.ndarray:
    v = salida.reshape(-1)
    _exigir_largo(v, len(s.etiquetas))
    return _softmax(v)


def _desde_probabilidades(salida: np.ndarray, s: EspecSalida) -> np.ndarray:
    v = salida.reshape(-1)
    _exigir_largo(v, len(s.etiquetas))
    total = float(v.sum())
    return v / total if total > 0 else v


def _desde_logit_sigmoide(salida: np.ndarray, s: EspecSalida) -> np.ndarray:
    v = salida.reshape(-1)
    _exigir_largo(v, 1)
    p_pos = float(1.0 / (1.0 + np.exp(-v[0])))
    idx_pos = s.etiquetas.index(s.positiva)  # type: ignore[arg-type]
    probas = np.zeros(2, dtype=np.float32)
    probas[idx_pos] = p_pos
    probas[1 - idx_pos] = 1.0 - p_pos
    return probas


def _exigir_largo(v: np.ndarray, esperado: int) -> None:
    if v.shape[0] != esperado:
        raise ModeloIncompatible(f"la salida tiene {v.shape[0]} valores y el contrato espera {esperado}")


REGISTRO: dict[str, Callable[[np.ndarray, EspecSalida], np.ndarray]] = {
    "logits": _desde_logits,
    "probabilidades": _desde_probabilidades,
    "logit_sigmoide": _desde_logit_sigmoide,
}


def posprocesar(salida: np.ndarray, s: EspecSalida) -> Prediccion:
    probas = REGISTRO[s.tipo](salida, s)
    if s.tipo == "logit_sigmoide":
        idx_pos = s.etiquetas.index(s.positiva)  # type: ignore[arg-type]
        elegido = idx_pos if probas[idx_pos] >= s.umbral else 1 - idx_pos
    else:
        elegido = int(np.argmax(probas))
    return Prediccion(
        prediccion=s.etiquetas[elegido],
        probabilidades={et: round(float(p), 6) for et, p in zip(s.etiquetas, probas)},
    )
