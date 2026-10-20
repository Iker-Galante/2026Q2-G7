"""Artefactos de demo: descarga fijada, verificación y carga idempotente en S3/MinIO."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

NOMBRE = "torax-rx-neumonia"
VERSION = "1.0.0"
PREFIJO = f"modelos/{NOMBRE}/{VERSION}/"
ESTADO = "demo/estado.json"
LISTO = "demo/artefactos.json"
RAIZ = Path(__file__).resolve().parents[1]
MODELO_DIR = RAIZ / "models" / NOMBRE / VERSION
log = logging.getLogger(__name__)


def sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def leer(s3, bucket: str, key: str) -> bytes | None:
    try:
        with s3.get_object(Bucket=bucket, Key=key)["Body"] as body:
            return body.read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404", "NotFound"):
            return None
        raise


def escribir_json(s3, bucket: str, key: str, datos: dict) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(datos).encode(), ContentType="application/json")


def manifiesto_modelo() -> dict:
    return json.loads((MODELO_DIR / "manifest.json").read_text())


def comprobar(datos: bytes, ref: dict) -> None:
    if len(datos) != ref["bytes"] or sha(datos) != ref["sha256"]:
        raise ValueError("El artefacto no coincide con el tamaño y SHA-256 fijados; no se sobrescribe")


def modelo_local(cache: Path) -> dict[str, bytes]:
    salida = {}
    for nombre, ref in manifiesto_modelo()["archivos"].items():
        archivo = MODELO_DIR / nombre
        if not archivo.exists():
            archivo = cache / nombre
        if not archivo.exists():
            archivo.parent.mkdir(parents=True, exist_ok=True)
            log.info("descargando %s de la revisión fijada", nombre)
            with urllib.request.urlopen(ref["url"], timeout=120) as r:
                datos = r.read()
            comprobar(datos, ref)
            temporal = archivo.with_suffix(".part")
            temporal.write_bytes(datos)
            temporal.replace(archivo)
        datos = archivo.read_bytes()
        comprobar(datos, ref)
        salida[nombre] = datos
    return salida


def validar_conjunto(leer_archivo) -> dict:
    """Comprueba etiquetas, cantidad, archivos y hash real, no solo el manifiesto."""
    m = json.loads(leer_archivo("manifiesto.json"))
    filas = [json.loads(linea) for linea in leer_archivo("verdad.jsonl").decode().splitlines() if linea.strip()]
    nombres = [f["caso"] for f in filas]
    if len(filas) != 200 or m["casos"] != 200 or len(set(nombres)) != 200:
        raise ValueError("El conjunto de demo debe contener 200 casos únicos")
    if any(n != Path(n).name or not n.endswith(".png") for n in nombres):
        raise ValueError("Nombre de caso inválido")
    if any(sum(f["etiqueta"] == c for f in filas) != 100 for c in ("NORMAL", "PNEUMONIA")):
        raise ValueError("Se requieren 100 casos por clase")
    h = hashlib.sha256()
    for nombre in sorted(nombres):
        datos = leer_archivo("casos/" + nombre)
        if not datos:
            raise ValueError("Caso vacío")
        h.update(sha(datos).encode())
    if m["hash"] != "sha256:" + h.hexdigest():
        raise ValueError("El hash del conjunto no coincide")
    return m


def preparar(s3, bucket_modelos: str, bucket_evaluacion: str, cache: Path) -> None:
    escribir_json(s3, bucket_modelos, ESTADO, {"estado": "preparando"})
    # Invalidar la marca antes de reparar: nadie registra una carga incompleta.
    s3.delete_object(Bucket=bucket_modelos, Key=LISTO)
    refs = manifiesto_modelo()["archivos"]
    faltan = []
    for nombre, ref in refs.items():
        remoto = leer(s3, bucket_modelos, PREFIJO + nombre)
        if remoto is None:
            faltan.append(nombre)
        elif nombre == "modelo.json":
            # La publicación existente puede haber formateado el mismo JSON de otra forma.
            if json.loads(remoto) != json.loads((MODELO_DIR / nombre).read_text()):
                raise ValueError("Ya existe un contrato distinto bajo la misma versión")
        else:
            comprobar(remoto, ref)
    if faltan:
        locales = modelo_local(cache / "modelo")
        for nombre in faltan:
            s3.put_object(Bucket=bucket_modelos, Key=PREFIJO + nombre, Body=locales[nombre],
                          ContentType="application/json" if nombre.endswith(".json") else "application/octet-stream")

    def remoto(nombre):
        datos = leer(s3, bucket_evaluacion, "torax-rx/v1/" + nombre)
        if datos is None:
            raise FileNotFoundError(nombre)
        return datos

    try:
        conjunto = validar_conjunto(remoto)
        log.info("conjunto remoto íntegro: se conserva sin descargar de nuevo")
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        carpeta = cache / "torax-rx" / "v1"
        try:
            conjunto = validar_conjunto(lambda nombre: (carpeta / nombre).read_bytes())
        except (OSError, ValueError, KeyError, TypeError):
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "tools.preparar_conjunto", "--hf",
                            "hf-vision/chest-xray-pneumonia", "--split", "test", "--por-clase", "100",
                            "--sin-optimizar", "--salida", str(carpeta)], check=True)
            conjunto = validar_conjunto(lambda nombre: (carpeta / nombre).read_bytes())
        # El manifiesto siempre se publica al final.
        s3.delete_object(Bucket=bucket_evaluacion, Key="torax-rx/v1/manifiesto.json")
        filas = [json.loads(v) for v in (carpeta / "verdad.jsonl").read_text().splitlines()]
        for nombre in [*("casos/" + f["caso"] for f in filas), "verdad.jsonl", "manifiesto.json"]:
            s3.upload_file(str(carpeta / nombre), bucket_evaluacion, "torax-rx/v1/" + nombre)
        validar_conjunto(remoto)
    escribir_json(s3, bucket_modelos, LISTO, {"modelo_sha256": refs["modelo.onnx"]["sha256"],
                                             "conjunto_hash": conjunto["hash"]})
    escribir_json(s3, bucket_modelos, ESTADO, {"estado": "listo"})
    log.info("artefactos verificados y listos para publicación automática")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, default=Path("/salida"))
    a = p.parse_args()
    if os.environ.get("DATOS_DEMO", "true").lower() != "true":
        return
    local = os.environ.get("AWS_ENDPOINT_URL_S3")
    s3 = boto3.client("s3", config=Config(connect_timeout=10, read_timeout=60,
                     s3={"addressing_style": "path" if local else "auto"}))
    bucket = os.environ["BUCKET_MODELOS"]
    for intento in range(3):
        try:
            preparar(s3, bucket, os.environ["BUCKET_EVALUACION"], a.cache)
            return
        except Exception:
            log.exception("falló la preparación de demo (intento %s/3)", intento + 1)
            escribir_json(s3, bucket, ESTADO, {"estado": "error"})
            if intento == 2:
                raise
            time.sleep(10)


if __name__ == "__main__":
    main()
