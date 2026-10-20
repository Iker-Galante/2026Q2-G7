"""Integración optativa contra una base exclusiva de pruebas, nunca la del usuario."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.demo import InicializarDemo, InicializarModelo, estado_demo
from app.infraestructura.postgres import migraciones
from app.infraestructura.postgres.conexion import crear_pool
from tools.demo_assets import catalogo, escribir_json
from test_demo_assets import S3

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DEMO_DATABASE_URL"), reason="requiere base exclusiva de integración")


@pytest.fixture
def entorno():
    url = os.environ["TEST_DEMO_DATABASE_URL"]
    migraciones.aplicar(url, Path("migraciones"))
    pool = crear_pool(url, maximo=6)
    pool.open(wait=True)
    with pool.connection() as conn:
        conn.execute("truncate demo_inicializacion, modelo cascade")
    s3 = S3()
    for md in catalogo():
        s3.put_object(Bucket="modelos", Key=md.prefijo + "modelo.json", Body=(md.directorio / "modelo.json").read_bytes())
    s = SimpleNamespace(bucket_modelos="modelos", prefijo_modelos="modelos/", cola_evaluaciones_url="demo", demo_reenvio_segundos=900, datos_demo=True)
    yield pool, s3, s
    pool.close()


class Sqs:
    def __init__(self, fallar=False):
        self.mensajes = []
        self.fallar = fallar

    def send_message(self, **kw):
        if self.fallar:
            raise RuntimeError("cola no disponible")
        self.mensajes.append(json.loads(kw["MessageBody"]))


def inicializador(entorno, sqs):
    pool, s3, s = entorno
    tarea = InicializarModelo(pool, s3, sqs, s, catalogo()[0])
    tarea.verificado = True  # La integridad S3 se prueba en test_demo_assets.
    return tarea


def test_dos_procesadores_y_reinicio_conservan_modelo(entorno):
    sqs = Sqs()
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(lambda _: inicializador(entorno, sqs).ejecutar(), range(2)))
    pool, _, _ = entorno
    with pool.connection() as conn:
        filas = conn.execute("select id, publicado from modelo").fetchall()
        assert len(filas) == 1
        conn.execute("update modelo set estado_evaluacion='ok', accuracy=0.9, metricas='{}'")
    inicializador(entorno, sqs).ejecutar()
    with pool.connection() as conn:
        assert conn.execute("select id, publicado from modelo").fetchall() == filas
    assert len(sqs.mensajes) == 1


def test_outbox_recupera_fallo_envio_y_limita_reintentos(entorno):
    sqs = Sqs(fallar=True)
    inicializador(entorno, sqs).ejecutar()
    pool, _, _ = entorno
    with pool.connection() as conn:
        assert conn.execute("select estado_evaluacion from modelo").fetchone()["estado_evaluacion"] == "pendiente"
    sqs.fallar = False
    inicializador(entorno, sqs).ejecutar()
    inicializador(entorno, sqs).ejecutar()
    assert len(sqs.mensajes) == 1
    with pool.connection() as conn:
        conn.execute("update demo_inicializacion set error=true, intentos=3 where clave=%s", (catalogo()[0].clave,))
    inicializador(entorno, sqs).ejecutar()
    assert len(sqs.mensajes) == 1


def test_pendiente_sin_mensaje_se_recupera(entorno):
    sqs = Sqs()
    inicializador(entorno, sqs).ejecutar()
    pool, _, _ = entorno
    with pool.connection() as conn:
        conn.execute("update demo_inicializacion set enviado=now()-interval '16 minutes'")
    inicializador(entorno, sqs).ejecutar()
    assert len(sqs.mensajes) == 2


def test_modelos_concurrentes_y_estado_parcial(entorno):
    n = len(catalogo())
    sqs = Sqs()
    pool, s3, s = entorno
    def ejecutar(_):
        manager = InicializarDemo(pool, s3, sqs, s)
        for t in manager.tareas:
            t.verificado = True
        manager.ejecutar()
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(ejecutar, range(2)))
    assert len(sqs.mensajes) == n
    assert len({m["modelo_id"] for m in sqs.mensajes}) == n
    with pool.connection() as conn:
        conn.execute("update modelo set estado_evaluacion='ok', accuracy=0.9 where nombre=%s", (catalogo()[0].nombre,))
        conn.execute("update modelo set estado_evaluacion='error' where nombre=%s", (catalogo()[1].nombre,))
    estado = estado_demo(s, pool, s3)
    assert (estado["estado"], estado["listos"], estado["errores"], estado["pendientes"]) == ("parcial", 1, 1, n - 2)
    ejecutar(0)
    assert len(sqs.mensajes) == n
    with pool.connection() as conn:
        conn.execute("update modelo set estado_evaluacion='ok', accuracy=0.9")
    assert estado_demo(s, pool, s3)["estado"] == "ok"
    s.datos_demo = False
    assert estado_demo(s, pool, s3)["estado"] == "desactivado"


def test_un_error_de_integridad_no_detiene_otros_modelos(entorno):
    pool, s3, s = entorno
    sqs = Sqs()
    md = catalogo()[0]
    escribir_json(s3, "modelos", md.listo, {"modelo_sha256": "incorrecto"})
    manager = InicializarDemo(pool, s3, sqs, s)
    for tarea in manager.tareas[1:]:
        tarea.verificado = True
    for _ in range(3):
        manager.ejecutar()
    assert len(sqs.mensajes) == len(catalogo()) - 1
    estado = estado_demo(s, pool, s3)
    assert estado["errores"] == 1
    assert estado["modelos"][0]["estado"] == "error"


def test_recuperacion_individual_conserva_otros_modelos(entorno, monkeypatch):
    from app import reintentar_demo as recuperar
    pool, s3, s = entorno
    sqs = Sqs()
    manager = InicializarDemo(pool, s3, sqs, s)
    for t in manager.tareas:
        t.verificado = True
    manager.ejecutar()
    md = catalogo()[1]
    with pool.connection() as conn:
        conn.execute("update modelo set estado_evaluacion='ok', accuracy=0.95")
        conn.execute("update modelo set estado_evaluacion='error' where nombre=%s", (md.nombre,))
        sanos = conn.execute("select id, publicado, accuracy from modelo where nombre<>%s order by id", (md.nombre,)).fetchall()
    def inicializador(*args):
        t = InicializarModelo(*args)
        t.verificado = True
        return t
    monkeypatch.setattr(recuperar, "InicializarModelo", inicializador)
    recuperar.reintentar(s, pool, s3, sqs, md)
    assert len(sqs.mensajes) == len(catalogo()) + 1
    assert sqs.mensajes[-1]["nombre"] == md.nombre
    with pool.connection() as conn:
        assert conn.execute("select id, publicado, accuracy from modelo where nombre<>%s order by id", (md.nombre,)).fetchall() == sanos
