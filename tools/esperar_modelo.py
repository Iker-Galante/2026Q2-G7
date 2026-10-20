"""Espera hasta que la demo esté realmente evaluada. No crea recursos ni publica modelos."""
import argparse
import json
import time
import urllib.error
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://api:8080")
    p.add_argument("--timeout", type=float, default=1800)
    a = p.parse_args()
    limite = time.monotonic() + a.timeout
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(a.url.rstrip("/") + "/api/publico/demo", timeout=10) as r:
                estado = json.load(r)
            print(estado, flush=True)
            if estado["estado"] == "ok":
                return
            if estado["estado"] in ("error", "desactivado"):
                raise SystemExit("Demo no disponible. Revisá los logs de demo-init, procesador y evaluador.")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Esperando API: {e}", flush=True)
        time.sleep(min(5, max(0, limite - time.monotonic())))
    raise SystemExit("Tiempo de espera agotado; la demo todavía no está lista")


if __name__ == "__main__":
    main()
