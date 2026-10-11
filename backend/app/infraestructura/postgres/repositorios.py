"""Repositorios con SQL explícito. Cada método es una transacción corta.

No hay transacciones largas a propósito: la llamada al worker (hasta 30 s)
nunca puede quedar adentro de una.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from ...dominio.errores import NoEncontrado
from ...dominio.estudio import Estudio
from ...dominio.modelo import Modelo
from ...dominio.trabajo import Trabajo


def _float(v: Any) -> float | None:
    return float(v) if isinstance(v, Decimal) else v


# ---- modelo -------------------------------------------------------------------------

COLUMNAS_MODELO = """id, nombre, version, tipo_estudio, tarea, etiquetas, s3_prefix, contrato,
    estado_evaluacion, accuracy, metricas, conjunto, conjunto_version, manifiesto,
    evaluador_id, evaluado_en, error, creado, publicado"""


def _fila_a_modelo(f: dict[str, Any]) -> Modelo:
    return Modelo(
        id=f["id"], nombre=f["nombre"], version=f["version"], tipo_estudio=f["tipo_estudio"],
        tarea=f["tarea"], etiquetas=list(f["etiquetas"]), s3_prefix=f["s3_prefix"], contrato=f["contrato"],
        estado_evaluacion=f["estado_evaluacion"], accuracy=_float(f["accuracy"]), metricas=f["metricas"],
        conjunto=f["conjunto"], conjunto_version=f["conjunto_version"], manifiesto=f["manifiesto"],
        evaluador_id=f["evaluador_id"], evaluado_en=f["evaluado_en"], error=f["error"],
        creado=f["creado"], publicado=f["publicado"],
    )


class RepositorioModelosPostgres:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def guardar(self, m: Modelo) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                f"""
                insert into modelo ({COLUMNAS_MODELO})
                values (%(id)s, %(nombre)s, %(version)s, %(tipo_estudio)s, %(tarea)s, %(etiquetas)s,
                        %(s3_prefix)s, %(contrato)s, %(estado_evaluacion)s, %(accuracy)s, %(metricas)s,
                        %(conjunto)s, %(conjunto_version)s, %(manifiesto)s, %(evaluador_id)s,
                        %(evaluado_en)s, %(error)s, %(creado)s, %(publicado)s)
                on conflict (id) do update set
                    tipo_estudio = excluded.tipo_estudio, tarea = excluded.tarea,
                    etiquetas = excluded.etiquetas, contrato = excluded.contrato,
                    estado_evaluacion = excluded.estado_evaluacion, accuracy = excluded.accuracy,
                    metricas = excluded.metricas, conjunto = excluded.conjunto,
                    conjunto_version = excluded.conjunto_version, manifiesto = excluded.manifiesto,
                    evaluador_id = excluded.evaluador_id, evaluado_en = excluded.evaluado_en,
                    error = excluded.error, publicado = excluded.publicado
                """,
                {
                    "id": m.id, "nombre": m.nombre, "version": m.version, "tipo_estudio": m.tipo_estudio,
                    "tarea": m.tarea, "etiquetas": Jsonb(m.etiquetas), "s3_prefix": m.s3_prefix,
                    "contrato": Jsonb(m.contrato), "estado_evaluacion": m.estado_evaluacion,
                    "accuracy": m.accuracy, "metricas": Jsonb(m.metricas) if m.metricas is not None else None,
                    "conjunto": m.conjunto, "conjunto_version": m.conjunto_version,
                    "manifiesto": Jsonb(m.manifiesto) if m.manifiesto is not None else None,
                    "evaluador_id": m.evaluador_id, "evaluado_en": m.evaluado_en, "error": m.error,
                    "creado": m.creado, "publicado": m.publicado,
                },
            )

    def obtener(self, id: UUID) -> Modelo:
        with self._pool.connection() as conn:
            fila = conn.execute(f"select {COLUMNAS_MODELO} from modelo where id = %s", (id,)).fetchone()
        if fila is None:
            raise NoEncontrado(f"no existe el modelo {id}")
        return _fila_a_modelo(fila)

    def buscar(self, nombre: str, version: str) -> Modelo | None:
        with self._pool.connection() as conn:
            fila = conn.execute(
                f"select {COLUMNAS_MODELO} from modelo where nombre = %s and version = %s", (nombre, version)
            ).fetchone()
        return _fila_a_modelo(fila) if fila else None

    def listar(self) -> list[Modelo]:
        with self._pool.connection() as conn:
            filas = conn.execute(f"select {COLUMNAS_MODELO} from modelo order by publicado desc").fetchall()
        return [_fila_a_modelo(f) for f in filas]


# ---- estudio ------------------------------------------------------------------------

COLUMNAS_ESTUDIO = "id, tipo_estudio, s3_key, content_type, tamano_bytes, estado, creado"


def _fila_a_estudio(f: dict[str, Any]) -> Estudio:
    return Estudio(id=f["id"], tipo_estudio=f["tipo_estudio"], s3_key=f["s3_key"],
                   content_type=f["content_type"], tamano_bytes=f["tamano_bytes"],
                   estado=f["estado"], creado=f["creado"])


class RepositorioEstudiosPostgres:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def guardar(self, e: Estudio) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                f"""
                insert into estudio ({COLUMNAS_ESTUDIO})
                values (%(id)s, %(tipo_estudio)s, %(s3_key)s, %(content_type)s, %(tamano_bytes)s, %(estado)s, %(creado)s)
                on conflict (id) do update set tamano_bytes = excluded.tamano_bytes, estado = excluded.estado
                """,
                {"id": e.id, "tipo_estudio": e.tipo_estudio, "s3_key": e.s3_key, "content_type": e.content_type,
                 "tamano_bytes": e.tamano_bytes, "estado": e.estado, "creado": e.creado},
            )

    def obtener(self, id: UUID) -> Estudio:
        with self._pool.connection() as conn:
            fila = conn.execute(f"select {COLUMNAS_ESTUDIO} from estudio where id = %s", (id,)).fetchone()
        if fila is None:
            raise NoEncontrado(f"no existe el estudio {id}")
        return _fila_a_estudio(fila)


# ---- trabajo ------------------------------------------------------------------------

COLUMNAS_TRABAJO = "id, estudio_id, modelo_id, estado, intentos, worker_id, resultado, duracion_ms, error, creado, actualizado"


def _fila_a_trabajo(f: dict[str, Any]) -> Trabajo:
    return Trabajo(id=f["id"], estudio_id=f["estudio_id"], modelo_id=f["modelo_id"], estado=f["estado"],
                   intentos=f["intentos"], worker_id=f["worker_id"], resultado=f["resultado"],
                   duracion_ms=f["duracion_ms"], error=f["error"], creado=f["creado"], actualizado=f["actualizado"])


class RepositorioTrabajosPostgres:
    """Repositorio y cola a la vez: son la misma tabla."""

    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def guardar(self, t: Trabajo) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                f"""
                insert into trabajo ({COLUMNAS_TRABAJO})
                values (%(id)s, %(estudio_id)s, %(modelo_id)s, %(estado)s, %(intentos)s, %(worker_id)s,
                        %(resultado)s, %(duracion_ms)s, %(error)s, %(creado)s, %(actualizado)s)
                on conflict (id) do update set
                    estado = excluded.estado, intentos = excluded.intentos, worker_id = excluded.worker_id,
                    resultado = excluded.resultado, duracion_ms = excluded.duracion_ms,
                    error = excluded.error, actualizado = excluded.actualizado
                """,
                {"id": t.id, "estudio_id": t.estudio_id, "modelo_id": t.modelo_id, "estado": t.estado,
                 "intentos": t.intentos, "worker_id": t.worker_id,
                 "resultado": Jsonb(t.resultado) if t.resultado is not None else None,
                 "duracion_ms": t.duracion_ms, "error": t.error, "creado": t.creado, "actualizado": t.actualizado},
            )

    def obtener(self, id: UUID) -> Trabajo:
        with self._pool.connection() as conn:
            fila = conn.execute(f"select {COLUMNAS_TRABAJO} from trabajo where id = %s", (id,)).fetchone()
        if fila is None:
            raise NoEncontrado(f"no existe el trabajo {id}")
        return _fila_a_trabajo(fila)

    # ---- ColaTrabajos ----

    def tomar_pendiente(self, max_intentos: int) -> Trabajo | None:
        with self._pool.connection() as conn:
            fila = conn.execute(
                f"""
                update trabajo set estado = 'en_curso', intentos = intentos + 1, actualizado = now()
                 where id = (select id from trabajo
                              where estado = 'pendiente' and intentos < %s
                              order by actualizado
                              for update skip locked
                              limit 1)
                returning {COLUMNAS_TRABAJO}
                """,
                (max_intentos,),
            ).fetchone()
        return _fila_a_trabajo(fila) if fila else None

    def reencolar_huerfanos(self, minutos: int) -> int:
        with self._pool.connection() as conn:
            cur = conn.execute(
                """
                update trabajo set estado = 'pendiente', actualizado = now(),
                       error = coalesce(error, '') || ' [huérfano reencolado]'
                 where estado = 'en_curso' and actualizado < now() - make_interval(mins => %s)
                """,
                (minutos,),
            )
            return cur.rowcount

    # ---- TrabajosSinEnviar (modo sqs) ----

    def tomar_para_reenviar(self, minutos: int, limite: int) -> list[Trabajo]:
        """Atómico: tocar `actualizado` hace que otro backend no los reenvíe en la misma vuelta."""
        with self._pool.connection() as conn:
            filas = conn.execute(
                f"""
                update trabajo set actualizado = now()
                 where id in (select id from trabajo
                               where estado = 'pendiente' and actualizado < now() - make_interval(mins => %s)
                               order by actualizado
                               for update skip locked
                               limit %s)
                returning {COLUMNAS_TRABAJO}
                """,
                (minutos, limite),
            ).fetchall()
        return [_fila_a_trabajo(f) for f in filas]

    def vencer_en_curso(self, minutos: int, motivo: str) -> int:
        with self._pool.connection() as conn:
            cur = conn.execute(
                """
                update trabajo set estado = 'error', error = %s, actualizado = now()
                 where estado = 'en_curso' and actualizado < now() - make_interval(mins => %s)
                """,
                (motivo, minutos),
            )
            return cur.rowcount
