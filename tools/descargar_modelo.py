#!/usr/bin/env python3
"""Baja el modelo ONNX elegido, escribe su `modelo.json` y lo sube a S3.

Es la "subida a mano" del pre-MVP: lo que en el producto real haría un publicador
desde la web. Después, el botón «Publicar modelo» de la pantalla hace el resto.

Uso:
  python tools/descargar_modelo.py                       # baja + sube a $BUCKET_MODELOS
  python tools/descargar_modelo.py --carpeta ./tmp/modelo --solo-descargar
  python tools/descargar_modelo.py --contrato            # imprime el modelo.json y sale

En CloudShell, sin tocar el disco:
  . infra/entorno.sh                                   # tus nombres de bucket
  P=s3://$BUCKET_MODELOS/modelos/torax-rx-neumonia/1.0.0
  curl -sL <URL_ONNX> | aws s3 cp - $P/modelo.onnx
  python3 tools/descargar_modelo.py --contrato | aws s3 cp - $P/modelo.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

# Modelo elegido (specs.md §2, D2): 16 MB, clasificación binaria de radiografía de tórax.
# El contrato de abajo NO está adivinado: se verificó contra el grafo (nombres y formas de
# los tensores) y contra 30 casos etiquetados del split de test, donde acertó los 30.
# Ver tools/verificar_modelo.py, que repite esa comprobación.
URL_ONNX = "https://huggingface.co/Rhishamah/mediscan-pneumonia/resolve/main/mediscan_pneumonia.onnx"
NOMBRE = "torax-rx-neumonia"
VERSION = "1.0.0"

MODELO_JSON = {
    "nombre": NOMBRE,
    "version": VERSION,
    "tipo_estudio": "torax-rx",
    "tarea": "clasificacion",
    "origen": "https://huggingface.co/Rhishamah/mediscan-pneumonia · CNN 16 MB · Kaggle Chest X-Ray Images (Pneumonia)",
    "entrada": {
        "nombre": "input",
        "layout": "NCHW",
        "forma": [1, 3, 224, 224],
        "dtype": "float32",
        "espacio_color": "RGB",
        "redimension": "estirar",
        "escala": 255,
        "media": [0.485, 0.456, 0.406],     # normalización ImageNet (verificada empíricamente)
        "desvio": [0.229, 0.224, 0.225],
    },
    "salida": {
        "nombre": "output",
        "tipo": "logit_sigmoide",           # un solo valor: sigmoide alto = neumonía
        "etiquetas": ["NORMAL", "PNEUMONIA"],
        "positiva": "PNEUMONIA",
        "umbral": 0.5,
    },
}


def descargar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size > 1_000_000:
        print(f"  ya existe {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
        return
    print(f"  bajando {url}")
    urllib.request.urlretrieve(url, destino)
    print(f"  {destino} · {destino.stat().st_size / 1e6:.1f} MB")


def subir(carpeta: Path, bucket: str) -> None:
    import boto3
    from botocore.config import Config

    s3 = boto3.client("s3", config=Config(
        s3={"addressing_style": "path" if os.environ.get("AWS_ENDPOINT_URL") else "auto"}))
    prefix = f"modelos/{NOMBRE}/{VERSION}/"
    for archivo in ("modelo.json", "modelo.onnx"):
        print(f"  subiendo s3://{bucket}/{prefix}{archivo}")
        s3.upload_file(str(carpeta / archivo), bucket, f"{prefix}{archivo}")
    print("listo · ahora apretá «Publicar modelo» en la pantalla")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--carpeta", default="./tmp/modelo")
    p.add_argument("--solo-descargar", action="store_true")
    p.add_argument("--solo-subir", action="store_true")
    p.add_argument("--contrato", action="store_true", help="imprime modelo.json por stdout y sale")
    a = p.parse_args()

    if a.contrato:
        print(json.dumps(MODELO_JSON, indent=2, ensure_ascii=False))
        return 0

    carpeta = Path(a.carpeta)
    if not a.solo_subir:
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "modelo.json").write_text(json.dumps(MODELO_JSON, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
        descargar(URL_ONNX, carpeta / "modelo.onnx")
    if not a.solo_descargar:
        bucket = os.environ.get("BUCKET_MODELOS")
        if not bucket:
            print("falta BUCKET_MODELOS (o usá --solo-descargar)", file=sys.stderr)
            return 2
        subir(carpeta, bucket)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
