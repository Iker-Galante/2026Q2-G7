from pathlib import Path

import pytest

from ateneo_ml.contrato import ContratoInvalido, ContratoModelo

RAIZ = Path(__file__).resolve().parent.parent


def test_contrato_valido(contrato_dict):
    c = ContratoModelo.desde_json(contrato_dict)
    assert c.nombre == "prueba"
    assert c.entrada.alto == 4 and c.entrada.ancho == 4 and c.entrada.canales == 3
    assert c.salida.etiquetas == ("NORMAL", "PNEUMONIA")
    assert c.es_binario


def test_nhwc_calcula_dimensiones(contrato_dict):
    contrato_dict["entrada"].update({"layout": "NHWC", "forma": [1, 6, 5, 3]})
    c = ContratoModelo.desde_json(contrato_dict)
    assert (c.entrada.alto, c.entrada.ancho, c.entrada.canales) == (6, 5, 3)


@pytest.mark.parametrize(
    "romper, fragmento",
    [
        (lambda d: d.pop("salida"), "salida"),
        (lambda d: d["entrada"].update({"forma": [2, 3, 4, 4]}), "batch"),
        (lambda d: d["entrada"].update({"espacio_color": "L"}), "canal"),
        (lambda d: d["entrada"].update({"media": [0.5]}), "canales"),
        (lambda d: d["entrada"].update({"desvio": None}), "juntos"),
        (lambda d: d["salida"].update({"etiquetas": ["A", "A"]}), "repetidas"),
        (lambda d: d["salida"].update({"positiva": "OTRA"}), "positiva"),
        (lambda d: d["salida"].update({"tipo": "raro"}), "salida.tipo"),
        (lambda d: d.update({"tarea": "segmentacion"}), "tarea"),
    ],
)
def test_contratos_invalidos(contrato_dict, romper, fragmento):
    romper(contrato_dict)
    with pytest.raises(ContratoInvalido) as e:
        ContratoModelo.desde_json(contrato_dict)
    assert fragmento in str(e.value)


def test_la_copia_del_backend_es_identica():
    """El backend valida modelo.json sin traer onnxruntime: lleva una copia de contrato.py. Vigilada acá."""
    original = (RAIZ / "ateneo_ml" / "contrato.py").read_bytes()
    copia = (RAIZ / "backend" / "app" / "dominio" / "contrato.py").read_bytes()
    assert original == copia, "backend/app/dominio/contrato.py difiere de ateneo_ml/contrato.py: copialo de nuevo"
