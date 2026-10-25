import io
import json
import sys

import pytest

from tools import esperar_modelo as esperar


def respuesta(estado):
    return io.BytesIO(json.dumps(estado).encode())


def test_espera_todos_hasta_que_finalicen(monkeypatch):
    estados = iter([
        {"estado": "parcial", "errores": 0, "pendientes": 2},
        {"estado": "ok", "errores": 0, "pendientes": 0},
    ])
    llamadas = []
    def leer(*args, **kwargs):
        llamadas.append(args)
        return respuesta(next(estados))
    monkeypatch.setattr(esperar.urllib.request, "urlopen", leer)
    monkeypatch.setattr(esperar.time, "sleep", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["esperar", "--timeout", "10"])
    esperar.main()
    assert len(llamadas) == 2


def test_seleccion_individual_no_depende_de_otro_error(monkeypatch):
    estado = {"estado": "parcial", "errores": 1, "pendientes": 0,
              "modelos": [{"nombre": "dense", "version": "1.0.0", "estado": "ok"}]}
    monkeypatch.setattr(esperar.urllib.request, "urlopen", lambda *a, **k: respuesta(estado))
    monkeypatch.setattr(sys, "argv", ["esperar", "--nombre", "dense"])
    esperar.main()


def test_error_final_con_disponibilidad_parcial(monkeypatch):
    monkeypatch.setattr(esperar.urllib.request, "urlopen", lambda *a, **k: respuesta(
        {"estado": "parcial", "errores": 1, "pendientes": 0}))
    monkeypatch.setattr(sys, "argv", ["esperar"])
    with pytest.raises(SystemExit, match="no disponible"):
        esperar.main()
