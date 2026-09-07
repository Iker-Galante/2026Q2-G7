#!/usr/bin/env python3
"""Aplica las migraciones de `migraciones/*.sql` que falten, en orden.

Uso:  DATABASE_URL=postgresql://... python tools/migrar.py
En AWS se corre desde una instancia de la capa app (Session Manager), que es la
única con acceso a la base:  set -a; . /etc/ateneo.env; set +a; python3.11 tools/migrar.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

CARPETA = Path(__file__).resolve().parent.parent / "migraciones"


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("falta DATABASE_URL", file=sys.stderr)
        return 2
    archivos = sorted(CARPETA.glob("*.sql"))
    if not archivos:
        print(f"no hay migraciones en {CARPETA}", file=sys.stderr)
        return 2

    with psycopg.connect(url) as conn:
        conn.execute("create table if not exists migracion_aplicada (nombre text primary key, aplicada timestamptz not null default now())")
        aplicadas = {f[0] for f in conn.execute("select nombre from migracion_aplicada").fetchall()}
        for archivo in archivos:
            if archivo.name in aplicadas:
                print(f"  ya aplicada: {archivo.name}")
                continue
            print(f"  aplicando:   {archivo.name}")
            with conn.transaction():
                conn.execute(archivo.read_text(encoding="utf-8"))
                conn.execute("insert into migracion_aplicada (nombre) values (%s)", (archivo.name,))
    print("migraciones al día")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
