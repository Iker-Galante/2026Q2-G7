"""La API con casos de uso falsos (dependency_overrides): códigos HTTP y forma de las respuestas."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("WEB_DIR", "/no/existe")   # sin sitio estático en los tests

from app.aplicacion.casos_uso.modelos import SubidaModelo  # noqa: E402
from app.aplicacion.puertos import SubidaFirmada  # noqa: E402
from app.api import dependencias  # noqa: E402
from app.dominio.errores import Conflicto, NoAutenticado, NoEncontrado  # noqa: E402
from app.dominio.modelo import Modelo  # noqa: E402
from app.dominio.trabajo import Trabajo  # noqa: E402
from app.main import crear_app  # noqa: E402

from .fakes import RelojFijo  # noqa: E402


def _modelo() -> Modelo:
    t = RelojFijo().ahora()
    return Modelo(id=uuid4(), nombre="torax", version="1.0.0", tipo_estudio="torax-rx", tarea="clasificacion",
                  etiquetas=["NORMAL", "PNEUMONIA"], s3_prefix="modelos/torax/1.0.0/", contrato={},
                  estado_evaluacion="pendiente", creado=t, publicado=t)


class CasoFalso:
    def __init__(self, resultado=None, error=None):
        self.resultado, self.error, self.llamadas = resultado, error, []

    def ejecutar(self, *a, **k):
        self.llamadas.append((a, k))
        if self.error:
            raise self.error
        return self.resultado


@pytest.fixture
def cliente():
    app = crear_app()
    app.dependency_overrides[dependencias.dep_verificador] = lambda: None   # sin Cognito: anónimo
    yield app, TestClient(app)
    app.dependency_overrides.clear()


class VerificadorFalso:
    """Acepta solo el token "bueno"; cualquier otro es NoAutenticado, como un JWT vencido."""
    def __init__(self):
        self.vistos = []

    def verificar(self, token):
        self.vistos.append(token)
        if token != "bueno":
            raise NoAutenticado("token inválido")
        return "sub-123"


def test_health(cliente):
    _, c = cliente
    assert c.get("/health").json() == {"ok": True}
    assert "instancia" in c.get("/api/health").json()


def test_publicar_202(cliente):
    app, c = cliente
    caso = CasoFalso(resultado=_modelo())
    app.dependency_overrides[dependencias.dep_publicar_modelo] = lambda: caso
    r = c.post("/api/modelos/publicar", json={"nombre": "torax", "version": "1.0.0"})
    assert r.status_code == 202
    assert r.json()["estado_evaluacion"] == "pendiente" and r.json()["accuracy"] is None
    assert caso.llamadas == [(("torax", "1.0.0", None), {})]


def test_publicar_409_con_forma_de_error(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_publicar_modelo] = lambda: CasoFalso(error=Conflicto("ya está en_curso"))
    r = c.post("/api/modelos/publicar", json={"nombre": "torax", "version": "1.0.0"})
    assert r.status_code == 409 and r.json() == {"error": "conflicto", "detalle": "ya está en_curso"}


def test_publicar_422_por_validacion_pydantic(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_publicar_modelo] = lambda: CasoFalso(resultado=_modelo())
    r = c.post("/api/modelos/publicar", json={"nombre": "con espacios", "version": "1"})
    assert r.status_code == 422 and r.json()["error"] == "entrada_invalida"


def test_publicar_lleva_el_contrato_subido_al_caso_de_uso(cliente):
    app, c = cliente
    caso = CasoFalso(resultado=_modelo())
    app.dependency_overrides[dependencias.dep_publicar_modelo] = lambda: caso
    contrato = {"nombre": "torax", "version": "1.0.0"}
    r = c.post("/api/modelos/publicar", json={"nombre": "torax", "version": "1.0.0", "contrato": contrato})
    assert r.status_code == 202
    assert caso.llamadas == [(("torax", "1.0.0", contrato), {})]


def test_preparar_subida_201_con_la_firma(cliente):
    app, c = cliente
    firmada = SubidaFirmada(url="http://s3.local/modelos", campos={"key": "modelos/torax/2.0.0/modelo.onnx"})
    caso = CasoFalso(resultado=SubidaModelo(prefix="modelos/torax/2.0.0/", subida=firmada))
    app.dependency_overrides[dependencias.dep_preparar_subida] = lambda: caso
    r = c.post("/api/modelos/subidas", json={"nombre": "torax", "version": "2.0.0", "tamano_bytes": 16_000_000})
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["prefix"] == "modelos/torax/2.0.0/"
    assert cuerpo["subida"]["campos"]["key"].endswith("modelo.onnx")
    assert caso.llamadas == [(("torax", "2.0.0", 16_000_000), {})]


def test_preparar_subida_409_si_la_version_ya_existe(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_preparar_subida] = lambda: CasoFalso(error=Conflicto("ya hay un modelo"))
    r = c.post("/api/modelos/subidas", json={"nombre": "torax", "version": "1.0.0", "tamano_bytes": 16})
    assert r.status_code == 409 and r.json()["error"] == "conflicto"


def test_preparar_subida_422_sin_tamano(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_preparar_subida] = lambda: CasoFalso(resultado=None)
    r = c.post("/api/modelos/subidas", json={"nombre": "torax", "version": "2.0.0", "tamano_bytes": 0})
    assert r.status_code == 422 and r.json()["error"] == "entrada_invalida"


def test_modelo_404(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_consultar_modelo] = lambda: CasoFalso(error=NoEncontrado("nope"))
    assert c.get(f"/api/modelos/{uuid4()}").status_code == 404


def test_trabajo_respuesta(cliente):
    app, c = cliente
    t = Trabajo.nuevo(type("E", (), {"id": uuid4()})(), type("M", (), {"id": uuid4()})(), RelojFijo().ahora())
    app.dependency_overrides[dependencias.dep_consultar_trabajo] = lambda: CasoFalso(resultado=t)
    r = c.get(f"/api/trabajos/{t.id}")
    assert r.status_code == 200 and r.json()["estado"] == "pendiente" and r.json()["resultado"] is None


def test_ruta_desconocida_bajo_api_es_404_json(cliente):
    _, c = cliente
    r = c.get("/api/nada")
    assert r.status_code == 404

def test_con_cognito_sin_token_es_401(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_verificador] = lambda: VerificadorFalso()
    app.dependency_overrides[dependencias.dep_listar_modelos] = lambda: CasoFalso(resultado=[])
    r = c.get("/api/modelos")
    assert r.status_code == 401 and r.json()["error"] == "no_autenticado"


def test_con_cognito_token_invalido_es_401(cliente):
    app, c = cliente
    verificador = VerificadorFalso()
    app.dependency_overrides[dependencias.dep_verificador] = lambda: verificador
    app.dependency_overrides[dependencias.dep_listar_modelos] = lambda: CasoFalso(resultado=[])
    r = c.get("/api/modelos", headers={"Authorization": "Bearer vencido"})
    assert r.status_code == 401 and verificador.vistos == ["vencido"]


def test_con_cognito_token_valido_pasa(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_verificador] = lambda: VerificadorFalso()
    app.dependency_overrides[dependencias.dep_listar_modelos] = lambda: CasoFalso(resultado=[])
    r = c.get("/api/modelos", headers={"Authorization": "Bearer bueno"})
    assert r.status_code == 200 and r.json() == []


def test_health_no_pide_token(cliente):
    app, c = cliente
    app.dependency_overrides[dependencias.dep_verificador] = lambda: VerificadorFalso()
    assert c.get("/api/health").status_code == 200
