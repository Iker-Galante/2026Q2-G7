"""El worker escribe solo el estado de su trabajo. Una conexión por proceso (la imagen dorada
trae psycopg pero no psycopg_pool), en autocommit, que se rehace si se cae."""

from __future__ import annotations

import threading

import psycopg
from psycopg.types.json import Jsonb


class ResultadosPostgres:
    def __init__(self, database_url: str):
        self._url = database_url
        self._conn: psycopg.Connection | None = None
        self._candado = threading.Lock()

    def _ejecutar(self, sql: str, params: tuple) -> int:
        with self._candado:
            for intento in (1, 2):
                try:
                    if self._conn is None or self._conn.closed:
                        self._conn = psycopg.connect(self._url, autocommit=True, connect_timeout=5)
                    return self._conn.execute(sql, params).rowcount
                except psycopg.OperationalError:
                    self._conn = None
                    if intento == 2:
                        raise
        return 0

    def tomar(self, trabajo_id: str, worker: str) -> bool:
        return self._ejecutar(
            """update trabajo set estado = 'en_curso', intentos = intentos + 1, worker_id = %s, actualizado = now()
                where id = %s and estado in ('pendiente', 'en_curso')""",
            (worker, trabajo_id),
        ) == 1

    def terminar_ok(self, trabajo_id, worker, prediccion, probabilidades, duracion_ms) -> None:
        self._ejecutar(
            """update trabajo set estado = 'ok', resultado = %s, worker_id = %s, duracion_ms = %s,
                      error = null, actualizado = now()
                where id = %s and estado <> 'ok'""",
            (Jsonb({"prediccion": prediccion, "probabilidades": probabilidades}), worker, duracion_ms, trabajo_id),
        )

    def terminar_error(self, trabajo_id: str, motivo: str) -> None:
        self._ejecutar(
            "update trabajo set estado = 'error', error = %s, actualizado = now() where id = %s and estado <> 'ok'",
            (motivo, trabajo_id),
        )

    def reintentar(self, trabajo_id: str, motivo: str) -> None:
        self._ejecutar(
            "update trabajo set estado = 'pendiente', error = %s, actualizado = now() where id = %s and estado = 'en_curso'",
            (motivo, trabajo_id),
        )
