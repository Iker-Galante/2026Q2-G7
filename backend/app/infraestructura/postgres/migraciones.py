"""Aplica las migraciones de `migraciones/*.sql` que falten, en orden. Lo hace el procesador al
arrancar, con un candado de la base: si arrancan dos tareas a la vez, la segunda espera y
encuentra todo aplicado.

A mano (o en docker compose): `python -m app.infraestructura.postgres.migraciones`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

CANDADO = 820_826   # cualquier número fijo: identifica el candado de migraciones de Ateneo


def aplicar(database_url: str, carpeta: Path) -> list[str]:
    archivos = sorted(carpeta.glob("*.sql"))
    if not archivos:
        raise FileNotFoundError(f"no hay migraciones en {carpeta}")
    nuevas: list[str] = []
    with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
        conn.execute("select pg_advisory_lock(%s)", (CANDADO,))
        try:
            conn.execute("create table if not exists migracion_aplicada "
                         "(nombre text primary key, aplicada timestamptz not null default now())")
            aplicadas = {f[0] for f in conn.execute("select nombre from migracion_aplicada").fetchall()}
            for archivo in archivos:
                if archivo.name in aplicadas:
                    continue
                with conn.transaction():
                    conn.execute(archivo.read_text(encoding="utf-8"))
                    conn.execute("insert into migracion_aplicada (nombre) values (%s)", (archivo.name,))
                nuevas.append(archivo.name)
        finally:
            conn.execute("select pg_advisory_unlock(%s)", (CANDADO,))
    return nuevas


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("falta DATABASE_URL")
    nuevas = aplicar(url, Path(os.environ.get("MIGRACIONES_DIR", "/opt/ateneo/migraciones")))
    print("aplicadas: " + ", ".join(nuevas) if nuevas else "migraciones al día")
