"""Fixtures compartidas: un contrato de ejemplo y un ONNX diminuto generado en el test."""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

CONTRATO_BASE = {
    "nombre": "prueba",
    "version": "1.0.0",
    "tipo_estudio": "torax-rx",
    "tarea": "clasificacion",
    "entrada": {
        "nombre": "entrada", "layout": "NCHW", "forma": [1, 3, 4, 4], "dtype": "float32",
        "espacio_color": "RGB", "redimension": "estirar", "escala": 255,
        "media": [0.5, 0.5, 0.5], "desvio": [0.5, 0.5, 0.5],
    },
    "salida": {"nombre": "salida", "tipo": "logits", "etiquetas": ["NORMAL", "PNEUMONIA"], "positiva": "PNEUMONIA"},
}


@pytest.fixture
def contrato_dict() -> dict:
    return copy.deepcopy(CONTRATO_BASE)


@pytest.fixture
def onnx_diminuto(tmp_path: Path) -> Path:
    """Un grafo (1,3,4,4) → (1,2): suma global por canal 0 y 1 como logits. Sin entrenar nada."""
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    entrada = helper.make_tensor_value_info("entrada", TensorProto.FLOAT, [1, 3, 4, 4])
    salida = helper.make_tensor_value_info("salida", TensorProto.FLOAT, [1, 2])
    # Reduce a (1,3) sumando H y W, después proyecta a 2 logits con una matriz fija.
    reduce = helper.make_node("ReduceSum", ["entrada", "ejes"], ["porcanal"], keepdims=0)
    ejes = helper.make_tensor("ejes", TensorProto.INT64, [2], [2, 3])
    w = helper.make_tensor("w", TensorProto.FLOAT, [3, 2], np.array([[1, 0], [0, 1], [0, 0]], dtype=np.float32).flatten())
    matmul = helper.make_node("MatMul", ["porcanal", "w"], ["salida"])
    grafo = helper.make_graph([reduce, matmul], "diminuto", [entrada], [salida], initializer=[ejes, w])
    modelo = helper.make_model(grafo, opset_imports=[helper.make_opsetid("", 13)])
    modelo.ir_version = 8
    onnx.checker.check_model(modelo)
    ruta = tmp_path / "modelo.onnx"
    onnx.save(modelo, ruta)
    return ruta


@pytest.fixture
def imagen_png(tmp_path: Path) -> bytes:
    from PIL import Image
    import io

    img = Image.new("RGB", (8, 6), (255, 0, 0))     # rojo: el canal 0 domina → NORMAL
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
