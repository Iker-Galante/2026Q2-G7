import io

import numpy as np
import pytest
from PIL import Image

from ateneo_ml import ContratoModelo, Inferidor
from ateneo_ml.contrato import EspecSalida
from ateneo_ml.decodificadores import decodificador_para
from ateneo_ml.errores import ImagenIlegible, ModeloIncompatible
from ateneo_ml.metricas import auc_por_ranking, calcular_metricas
from ateneo_ml.motor import OnnxMotor
from ateneo_ml.postprocesamiento import posprocesar
from ateneo_ml.preprocesamiento import preprocesar


# ---- preprocesamiento ---------------------------------------------------------------

def test_preprocesar_nchw_normaliza(contrato_dict):
    c = ContratoModelo.desde_json(contrato_dict)
    img = Image.new("RGB", (10, 10), (255, 0, 0))
    t = preprocesar(img, c.entrada)
    assert t.shape == (1, 3, 4, 4) and t.dtype == np.float32
    assert np.allclose(t[0, 0], 1.0)     # (255/255 - 0.5) / 0.5
    assert np.allclose(t[0, 1], -1.0)    # (0 - 0.5) / 0.5


def test_preprocesar_nhwc_gris_replicado(contrato_dict):
    contrato_dict["entrada"].update({"layout": "NHWC", "forma": [1, 4, 4, 3], "espacio_color": "gris_replicado",
                                     "media": None, "desvio": None})
    c = ContratoModelo.desde_json(contrato_dict)
    img = Image.new("RGB", (4, 4), (255, 0, 0))
    t = preprocesar(img, c.entrada)
    assert t.shape == (1, 4, 4, 3)
    assert np.allclose(t[..., 0], t[..., 1]) and np.allclose(t[..., 1], t[..., 2])   # 3 canales iguales
    assert abs(float(t[0, 0, 0, 0]) - 0.299) < 0.01                                  # luma de rojo puro


def test_preprocesar_recorte_centro(contrato_dict):
    contrato_dict["entrada"].update({"redimension": "recortar_centro"})
    c = ContratoModelo.desde_json(contrato_dict)
    img = Image.new("RGB", (40, 8))
    assert preprocesar(img, c.entrada).shape == (1, 3, 4, 4)


# ---- decodificadores ----------------------------------------------------------------

def test_decodificar_png(imagen_png):
    img = decodificador_para("x.png").decodificar(imagen_png)
    assert img.size == (8, 6)


def test_decodificar_basura_falla():
    with pytest.raises(ImagenIlegible):
        decodificador_para("x.png").decodificar(b"no soy una imagen")


def test_extension_desconocida():
    with pytest.raises(ImagenIlegible):
        decodificador_para("x.dcm")


# ---- posprocesamiento ---------------------------------------------------------------

def test_posprocesar_logits():
    s = EspecSalida(nombre=None, tipo="logits", etiquetas=("a", "b", "c"), positiva=None)
    p = posprocesar(np.array([[1.0, 3.0, 1.0]]), s)
    assert p.prediccion == "b"
    assert abs(sum(p.probabilidades.values()) - 1) < 1e-5


def test_posprocesar_logit_sigmoide_con_umbral():
    s = EspecSalida(nombre=None, tipo="logit_sigmoide", etiquetas=("neg", "pos"), positiva="pos", umbral=0.9)
    p = posprocesar(np.array([[1.0]]), s)     # sigmoide(1) ≈ 0.73 < 0.9
    assert p.prediccion == "neg" and abs(p.probabilidades["pos"] - 0.731) < 0.01


def test_posprocesar_largo_incorrecto():
    s = EspecSalida(nombre=None, tipo="logits", etiquetas=("a", "b"), positiva=None)
    with pytest.raises(ModeloIncompatible):
        posprocesar(np.array([[1.0, 2.0, 3.0]]), s)


# ---- métricas -----------------------------------------------------------------------

def test_metricas_binarias_a_mano():
    verdades = ["P", "P", "P", "N", "N", "N"]
    predichas = ["P", "P", "N", "N", "N", "P"]
    m = calcular_metricas(verdades, predichas, ["N", "P"], prob_positiva=[0.9, 0.8, 0.4, 0.2, 0.1, 0.6], positiva="P")
    assert m["n_casos"] == 6
    assert m["accuracy"] == pytest.approx(4 / 6, abs=1e-4)
    assert m["sensibilidad"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["especificidad"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["precision"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["matriz_confusion"]["valores"] == [[2, 1], [1, 2]]
    assert m["auc"] == pytest.approx(8 / 9, abs=1e-4)


def test_auc_perfecta_y_empates():
    assert auc_por_ranking(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert auc_por_ranking(np.array([0, 1]), np.array([0.5, 0.5])) == 0.5


def test_metricas_multiclase():
    m = calcular_metricas(["a", "b", "c", "a"], ["a", "b", "a", "a"], ["a", "b", "c"])
    assert m["accuracy"] == 0.75
    assert m["por_clase"]["c"]["sensibilidad"] == 0.0
    assert "auc" not in m


# ---- motor + pipeline con un ONNX real diminuto -------------------------------------

def test_pipeline_completo(contrato_dict, onnx_diminuto, imagen_png):
    c = ContratoModelo.desde_json(contrato_dict)
    inferidor = Inferidor(c, OnnxMotor(str(onnx_diminuto), c, hilos=1))
    p = inferidor.inferir(imagen_png, "caso.png")
    assert p.prediccion == "NORMAL"                       # rojo → canal 0 → logit 0
    assert p.probabilidades["NORMAL"] > 0.99


def test_motor_resuelve_nombre_unico(contrato_dict, onnx_diminuto):
    contrato_dict["entrada"]["nombre"] = "nombre_equivocado"    # único input: se tolera con warning
    c = ContratoModelo.desde_json(contrato_dict)
    OnnxMotor(str(onnx_diminuto), c, hilos=1)


def test_motor_rechaza_forma_distinta(contrato_dict, onnx_diminuto):
    contrato_dict["entrada"]["forma"] = [1, 3, 8, 8]
    c = ContratoModelo.desde_json(contrato_dict)
    with pytest.raises(ModeloIncompatible):
        OnnxMotor(str(onnx_diminuto), c, hilos=1)


def test_pipeline_imagen_ilegible(contrato_dict, onnx_diminuto):
    c = ContratoModelo.desde_json(contrato_dict)
    inferidor = Inferidor(c, OnnxMotor(str(onnx_diminuto), c, hilos=1))
    with pytest.raises(ImagenIlegible):
        inferidor.inferir(b"xx", "caso.png")


def _png(color):
    img = Image.new("RGB", (4, 4), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
