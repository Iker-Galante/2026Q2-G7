"""Métricas de evaluación, solo con numpy (la imagen dorada no trae scikit-learn)."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def calcular_metricas(
    verdades: Sequence[str],
    predicciones: Sequence[str],
    etiquetas: Sequence[str],
    prob_positiva: Sequence[float] | None = None,
    positiva: str | None = None,
) -> dict:
    """Devuelve un dict serializable a JSON.

    - Siempre: n_casos, accuracy, matriz_confusion, macro (precision, sensibilidad, f1) y por clase.
    - Si hay `positiva` (binario): sensibilidad, especificidad, precision, f1 y, con `prob_positiva`, auc.
    """
    etiquetas = list(etiquetas)
    idx = {e: i for i, e in enumerate(etiquetas)}
    n = len(verdades)
    if n == 0:
        raise ValueError("no hay casos para calcular métricas")
    if len(predicciones) != n:
        raise ValueError("verdades y predicciones tienen distinto largo")

    k = len(etiquetas)
    matriz = np.zeros((k, k), dtype=np.int64)      # filas: verdad · columnas: predicción
    for v, p in zip(verdades, predicciones):
        matriz[idx[v], idx[p]] += 1

    tp = np.diag(matriz).astype(np.float64)
    fp = matriz.sum(axis=0) - tp
    fn = matriz.sum(axis=1) - tp
    precision_c = _div(tp, tp + fp)
    sensibilidad_c = _div(tp, tp + fn)
    f1_c = _div(2 * precision_c * sensibilidad_c, precision_c + sensibilidad_c)

    resultado: dict = {
        "n_casos": int(n),
        "accuracy": round(float(tp.sum() / n), 4),
        "precision_macro": round(float(precision_c.mean()), 4),
        "sensibilidad_macro": round(float(sensibilidad_c.mean()), 4),
        "f1_macro": round(float(f1_c.mean()), 4),
        "por_clase": {
            e: {
                "precision": round(float(precision_c[i]), 4),
                "sensibilidad": round(float(sensibilidad_c[i]), 4),
                "f1": round(float(f1_c[i]), 4),
                "soporte": int(matriz[i].sum()),
            }
            for i, e in enumerate(etiquetas)
        },
        "matriz_confusion": {"etiquetas": etiquetas, "valores": matriz.tolist()},
    }

    if positiva is not None and k == 2:
        ip = idx[positiva]
        ineg = 1 - ip
        tp_b, fn_b = matriz[ip, ip], matriz[ip, ineg]
        fp_b, tn_b = matriz[ineg, ip], matriz[ineg, ineg]
        sens = _div1(tp_b, tp_b + fn_b)
        esp = _div1(tn_b, tn_b + fp_b)
        prec = _div1(tp_b, tp_b + fp_b)
        resultado.update(
            {
                "positiva": positiva,
                "sensibilidad": round(sens, 4),
                "especificidad": round(esp, 4),
                "precision": round(prec, 4),
                "f1": round(_div1(2 * prec * sens, prec + sens), 4),
            }
        )
        if prob_positiva is not None:
            y = np.asarray([1 if v == positiva else 0 for v in verdades])
            resultado["auc"] = round(auc_por_ranking(y, np.asarray(prob_positiva, dtype=np.float64)), 4)

    return resultado


def auc_por_ranking(y: np.ndarray, score: np.ndarray) -> float:
    """AUC ROC como estadístico de Mann-Whitney, con empates promediados."""
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    orden = np.argsort(score, kind="mergesort")
    s = score[orden]
    rangos = np.empty(len(s), dtype=np.float64)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        rangos[i : j + 1] = (i + j + 2) / 2.0   # rango promedio, base 1
        i = j + 1
    suma_pos = rangos[y[orden] == 1].sum()
    return float((suma_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(b > 0, a / np.where(b > 0, b, 1), 0.0)
    return r.astype(np.float64)


def _div1(a: float, b: float) -> float:
    return float(a / b) if b else 0.0
