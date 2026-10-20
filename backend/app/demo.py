"""Registro interno de la demo; outbox transaccional y candado entre procesadores."""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager

from psycopg.types.json import Jsonb

from tools.demo_assets import ESTADO, LISTO, MODELO_DIR, NOMBRE, VERSION, PREFIJO, comprobar, escribir_json, leer, manifiesto_modelo

from .aplicacion.casos_uso.modelos import PublicarModelo
from .infraestructura.postgres.repositorios import RepositorioModelosPostgres
from .infraestructura.reloj import RelojSistema
from .infraestructura.s3.catalogo_modelos import CatalogoModelosS3

CLAVE = f"{NOMBRE}/{VERSION}"
log = logging.getLogger(__name__)


class ConexionPrestada:
    """Los repositorios participan de una única transacción de inicialización."""
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


class OutboxDemo:
    def __init__(self, conn):
        self.conn = conn

    def enviar(self, peticion):
        self.conn.execute("insert into demo_inicializacion (clave, mensaje) values (%s, %s)",
                          (CLAVE, Jsonb(peticion.como_mensaje())))


class InicializarDemo:
    def __init__(self, pool, s3, sqs, settings):
        self.pool, self.s3, self.sqs, self.settings = pool, s3, sqs, settings
        self.verificado = False
        self.terminado = False
        self.errores = 0

    def ejecutar(self):
        if self.terminado:
            return
        try:
            self._ejecutar()
            self.errores = 0
        except Exception:
            self.errores += 1
            if self.errores >= 3:
                escribir_json(self.s3, self.settings.bucket_modelos, ESTADO, {"estado": "error"})
                self.terminado = True
            raise

    def _ejecutar(self):
        s = self.settings
        if not self.verificado:
            marca = leer(self.s3, s.bucket_modelos, LISTO)
            if marca is None:
                return
            ref = manifiesto_modelo()["archivos"]["modelo.onnx"]
            if json.loads(marca)["modelo_sha256"] != ref["sha256"]:
                raise ValueError("La marca de demo pertenece a otro modelo")
            datos = leer(self.s3, s.bucket_modelos, PREFIJO + "modelo.onnx")
            if datos is None:
                return
            comprobar(datos, ref)
            contrato = leer(self.s3, s.bucket_modelos, PREFIJO + "modelo.json")
            if contrato is None or json.loads(contrato) != json.loads((MODELO_DIR / "modelo.json").read_text()):
                raise ValueError("El contrato de demo no coincide")
            self.verificado = True

        with self.pool.connection() as conn:
            if not conn.execute("select pg_try_advisory_xact_lock(82082026) as tomado").fetchone()["tomado"]:
                return
            modelos = RepositorioModelosPostgres(ConexionPrestada(conn))
            modelo = modelos.buscar(NOMBRE, VERSION)
            if modelo is not None:
                if modelo.contrato != json.loads((MODELO_DIR / "modelo.json").read_text()):
                    raise ValueError("El catálogo contiene otro contrato para la versión de demo")
                if modelo.estado_evaluacion in ("ok", "error"):
                    self.terminado = modelo.estado_evaluacion == "ok"
                    return
                if modelo.estado_evaluacion == "en_curso":
                    return
            else:
                caso = PublicarModelo(CatalogoModelosS3(self.s3, s.bucket_modelos), modelos,
                                      RelojSistema(), s.prefijo_modelos, OutboxDemo(conn))
                modelo = caso.ejecutar(NOMBRE, VERSION)
                log.info("demo registrada: %s; evaluación pendiente de envío", modelo.id)
            # Una publicación manual pendiente puede no tener outbox: esperar antes de recuperar.
            from .aplicacion.puertos import PeticionEvaluacion
            conn.execute("""insert into demo_inicializacion (clave, mensaje, intentos, enviado)
                            values (%s, %s, 1, now()) on conflict (clave) do nothing""",
                         (CLAVE, Jsonb(PeticionEvaluacion.de(modelo).como_mensaje())))
        # La fila del modelo y su mensaje ya están confirmados antes de enviar a SQS.
        with self.pool.connection() as conn:
            conn.execute("select pg_advisory_xact_lock(82082026)")
            fila = conn.execute("""select *, enviado is null or
                enviado < now() - make_interval(secs => %s) as vencido
                from demo_inicializacion where clave = %s for update""",
                (s.demo_reenvio_segundos, CLAVE)).fetchone()
            estado = conn.execute("select estado_evaluacion from modelo where nombre=%s and version=%s",
                                  (NOMBRE, VERSION)).fetchone()["estado_evaluacion"]
            if estado != "pendiente" or fila["intentos"] >= 3 or not (fila["vencido"] or fila["error"]):
                return
            try:
                self.sqs.send_message(QueueUrl=s.cola_evaluaciones_url, MessageBody=json.dumps(fila["mensaje"]))
                error = False
                log.info("evaluación demo encolada")
            except Exception:
                error = True
                log.exception("falló el envío de demo; reintento limitado")
            conn.execute("""update demo_inicializacion set intentos=intentos+1, enviado=now(), error=%s
                            where clave=%s""", (error, CLAVE))


def estado_demo(settings, pool, s3) -> dict:
    if not settings.datos_demo:
        return {"activo": False, "estado": "desactivado"}
    modelo = RepositorioModelosPostgres(pool).buscar(NOMBRE, VERSION)
    if modelo is not None and modelo.estado_evaluacion in ("ok", "error", "en_curso"):
        return {"activo": True, "estado": modelo.estado_evaluacion, "modelo_id": str(modelo.id)}
    with pool.connection() as conn:
        fila = conn.execute("select intentos from demo_inicializacion where clave=%s", (CLAVE,)).fetchone()
    if fila and fila["intentos"] >= 3:
        return {"activo": True, "estado": "error"}
    marca = leer(s3, settings.bucket_modelos, ESTADO)
    if marca and json.loads(marca).get("estado") == "error":
        return {"activo": True, "estado": "error"}
    return {"activo": True, "estado": "pendiente" if modelo else "preparando"}
