"""Integración optativa contra una base exclusiva de pruebas, nunca la del usuario."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.demo import CLAVE, InicializarDemo
from app.infraestructura.postgres import migraciones
from app.infraestructura.postgres.conexion import crear_pool
from tools.demo_assets import MODELO_DIR, NOMBRE, PREFIJO, VERSION
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
    s3.put_object(Bucket="modelos", Key=PREFIJO + "modelo.json", Body=(MODELO_DIR / "modelo.json").read_bytes())
    s = SimpleNamespace(bucket_modelos="modelos", prefijo_modelos="modelos/", cola_evaluaciones_url="demo", demo_reenvio_segundos=900)
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
    tarea = InicializarDemo(pool, s3, sqs, s)
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
        conn.execute("update demo_inicializacion set error=true, intentos=3 where clave=%s", (CLAVE,))
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
