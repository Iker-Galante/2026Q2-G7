"""Artefactos de demo: descarga fijada, verificación y carga idempotente en S3/MinIO."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
import tempfile
import urllib.request
from pathlib import Path
from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

RAIZ = Path(__file__).resolve().parents[1]
MODELS_DIR = RAIZ / "models"
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModeloDemo:
    nombre: str
    version: str
    nombre_visible: str
    manifiesto: str

    @property
    def clave(self):
        return f"{self.nombre}/{self.version}"

    @property
    def directorio(self):
        return (MODELS_DIR / self.manifiesto).parent

    @property
    def prefijo(self):
        return f"modelos/{self.clave}/"

    @property
    def estado(self):
        return f"demo/{self.clave}/estado.json"

    @property
    def listo(self):
        return f"demo/{self.clave}/artefactos.json"

    def metadata(self):
        m = json.loads((MODELS_DIR / self.manifiesto).read_text())
        if (m["nombre"], m["version"]) != (self.nombre, self.version):
            raise ValueError("La identidad del manifiesto no coincide con el registro")
        comprobar((self.directorio / "modelo.json").read_bytes(), m["archivos"]["modelo.json"])
        return m

    def contrato(self):
        self.metadata()
        return json.loads((self.directorio / "modelo.json").read_text())


def catalogo() -> list[ModeloDemo]:
    modelos = [ModeloDemo(**m) for m in json.loads((MODELS_DIR / "catalogo.json").read_text())]
    if not modelos or len({m.clave for m in modelos}) != len(modelos):
        raise ValueError("Registro vacío o con identidades duplicadas")
    for m in modelos:
        for segmento in (m.nombre, m.version):
            if not segmento or segmento in (".", "..") or "/" in segmento:
                raise ValueError("Identidad inválida")
        if m.manifiesto != f"{m.clave}/manifest.json":
            raise ValueError("Ruta de manifiesto inválida")
    return modelos


def seleccionar(nombre: str, version: str) -> ModeloDemo:
    for m in catalogo():
        if (m.nombre, m.version) == (nombre, version):
            return m
    raise ValueError("La identidad no pertenece al catálogo inicial")


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


def comprobar(datos: bytes, ref: dict) -> None:
    if len(datos) != ref["bytes"] or sha(datos) != ref["sha256"]:
        raise ValueError("El artefacto no coincide con el tamaño y SHA-256 fijados; no se sobrescribe")


def modelo_local(cache: Path, modelo: ModeloDemo) -> dict[str, bytes]:
    salida = {}
    for nombre, ref in modelo.metadata()["archivos"].items():
        archivo = modelo.directorio / nombre
        if not archivo.exists():
            archivo = cache / nombre
        if not archivo.exists():
            archivo.parent.mkdir(parents=True, exist_ok=True)
            log.info("descargando %s de la revisión fijada", nombre)
            with urllib.request.urlopen(ref["url"], timeout=120) as r:
                datos = r.read()
            comprobar(datos, ref)
            # Dos preparadores pueden compartir caché sin pisar sus descargas temporales.
            with tempfile.NamedTemporaryFile(dir=archivo.parent, suffix=".part", delete=False) as f:
                temporal = Path(f.name)
                f.write(datos)
            try:
                temporal.replace(archivo)
            finally:
                temporal.unlink(missing_ok=True)
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


def preparar_conjunto(s3, bucket_evaluacion: str, cache: Path) -> dict:
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
    return conjunto


def preparar_modelo(s3, bucket: str, cache: Path, modelo: ModeloDemo, conjunto_hash: str) -> None:
    escribir_json(s3, bucket, modelo.estado, {"estado": "preparando"})
    s3.delete_object(Bucket=bucket, Key=modelo.listo)
    refs = modelo.metadata()["archivos"]
    faltan = []
    for nombre, ref in refs.items():
        remoto = leer(s3, bucket, modelo.prefijo + nombre)
        if remoto is None:
            faltan.append(nombre)
        elif nombre == "modelo.json":
            # La API puede haber formateado el mismo contrato de otra forma.
            if json.loads(remoto) != modelo.contrato():
                raise ValueError("Ya existe un contrato distinto bajo la misma versión")
        else:
            comprobar(remoto, ref)
    if faltan:
        locales = modelo_local(cache / "modelos" / modelo.nombre / modelo.version, modelo)
        for nombre in faltan:
            s3.put_object(Bucket=bucket, Key=modelo.prefijo + nombre, Body=locales[nombre],
                          ContentType="application/json" if nombre.endswith(".json") else "application/octet-stream")
    escribir_json(s3, bucket, modelo.listo, {"modelo_sha256": refs["modelo.onnx"]["sha256"],
                                            "conjunto_hash": conjunto_hash})
    escribir_json(s3, bucket, modelo.estado, {"estado": "listo"})
    log.info("artefactos listos: %s", modelo.clave)


def marcar_error(s3, bucket, modelo, estado="error"):
    try:
        escribir_json(s3, bucket, modelo.estado, {"estado": estado})
    except Exception:
        log.exception("no se pudo guardar el estado de %s", modelo.clave)


def preparar(s3, bucket_modelos: str, bucket_evaluacion: str, cache: Path, modelos=None, final=True) -> dict[str, bool]:
    modelos = catalogo() if modelos is None else modelos
    try:
        conjunto = preparar_conjunto(s3, bucket_evaluacion, cache)
    except Exception:
        for modelo in modelos:
            marcar_error(s3, bucket_modelos, modelo, "error" if final else "preparando")
        raise
    resultado = {}
    for modelo in modelos:
        try:
            preparar_modelo(s3, bucket_modelos, cache, modelo, conjunto["hash"])
            resultado[modelo.clave] = True
        except Exception:
            log.exception("falló la preparación de %s; continúo con los otros", modelo.clave)
            marcar_error(s3, bucket_modelos, modelo, "error" if final else "preparando")
            resultado[modelo.clave] = False
    return resultado


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
    pendientes = catalogo()
    for intento in range(3):
        try:
            estados = preparar(s3, bucket, os.environ["BUCKET_EVALUACION"], a.cache, pendientes, final=intento == 2)
            pendientes = [m for m in pendientes if not estados[m.clave]]
            if not pendientes:
                return
        except Exception:
            log.exception("falló el conjunto compartido (intento %s/3)", intento + 1)
        if intento < 2:
            time.sleep(10)
    raise SystemExit("No se pudieron preparar todos los modelos iniciales; revisar los estados individuales")


if __name__ == "__main__":
    main()
