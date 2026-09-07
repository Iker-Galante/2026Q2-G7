"""La cola de modelos a evaluar es la tabla `modelo`, tomada con SKIP LOCKED.

Sin pool (psycopg_pool no está en la imagen dorada): una conexión corta por operación.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..puertos import ModeloPendiente, ResultadoEvaluacion


class ColaPostgres:
    def __init__(self, database_url: str, evaluador_id: str):
        self._url = database_url
        self._yo = evaluador_id

    def _conectar(self):
        return psycopg.connect(self._url, row_factory=dict_row, connect_timeout=10)

    def reencolar_en_curso(self) -> int:
        with self._conectar() as conn:
            return conn.execute(
                "update modelo set estado_evaluacion = 'pendiente' where estado_evaluacion = 'en_curso'"
            ).rowcount

    def tomar_pendiente(self) -> ModeloPendiente | None:
        with self._conectar() as conn:
            fila = conn.execute(
                """
                update modelo set estado_evaluacion = 'en_curso', evaluador_id = %s
                 where id = (select id from modelo where estado_evaluacion = 'pendiente'
                             order by publicado for update skip locked limit 1)
                returning id, nombre, version, tipo_estudio, s3_prefix, etiquetas
                """,
                (self._yo,),
            ).fetchone()
        if fila is None:
            return None
        return ModeloPendiente(id=fila["id"], nombre=fila["nombre"], version=fila["version"],
                               tipo_estudio=fila["tipo_estudio"], s3_prefix=fila["s3_prefix"],
                               etiquetas=list(fila["etiquetas"]))

    def terminar_ok(self, modelo: ModeloPendiente, r: ResultadoEvaluacion) -> None:
        with self._conectar() as conn:
            conn.execute(
                """
                update modelo set estado_evaluacion = 'ok', accuracy = %s, metricas = %s,
                       conjunto = %s, conjunto_version = %s, manifiesto = %s,
                       evaluador_id = %s, evaluado_en = %s, error = null
                 where id = %s
                """,
                (r.metricas["accuracy"], Jsonb(r.metricas), r.conjunto, r.conjunto_version,
                 Jsonb(r.manifiesto), self._yo, r.terminado, modelo.id),
            )

    def terminar_error(self, modelo: ModeloPendiente, motivo: str) -> None:
        with self._conectar() as conn:
            conn.execute(
                """
                update modelo set estado_evaluacion = 'error', error = %s, evaluador_id = %s, evaluado_en = now()
                 where id = %s
                """,
                (motivo[:2000], self._yo, modelo.id),
            )
