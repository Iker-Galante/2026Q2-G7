"""Pool de conexiones. Uno por proceso; lo abre y cierra `main.py`."""

from __future__ import annotations

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def crear_pool(database_url: str, minimo: int = 1, maximo: int = 4) -> ConnectionPool:
    return ConnectionPool(
        conninfo=database_url,
        min_size=minimo,
        max_size=maximo,
        open=False,
        kwargs={"row_factory": dict_row},
        timeout=10,
    )
