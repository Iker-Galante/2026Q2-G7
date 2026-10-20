#!/usr/bin/env python3
"""Arma un conjunto de evaluación: casos con nombre opaco, verdad.jsonl y manifiesto.json.

Dos orígenes posibles:

  # a) sin cuenta de Kaggle: el mismo dataset servido por Hugging Face
  python tools/preparar_conjunto.py --hf hf-vision/chest-xray-pneumonia --split test \
         --por-clase 100 --salida ./tmp/torax-rx/v1

  # b) una carpeta local con una subcarpeta por clase (p. ej. el zip de Kaggle descomprimido)
  python tools/preparar_conjunto.py ./datos/chest_xray/test --por-clase 100 --salida ./tmp/torax-rx/v1

Produce  <salida>/manifiesto.json · <salida>/verdad.jsonl · <salida>/casos/<uuid>.png
y se sube a  s3://<bucket-evaluacion>/<tipo-estudio>/<version>/  (guía §04).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import urllib.request
import uuid
from datetime import date
from pathlib import Path

from PIL import Image

EXTENSIONES = {".png", ".jpg", ".jpeg", ".bmp"}
SERVIDOR_HF = "https://datasets-server.huggingface.co"


def desde_carpeta(origen: Path, por_clase: int, rng: random.Random) -> list[tuple[str, bytes]]:
    clases = sorted(d.name for d in origen.iterdir() if d.is_dir())
    if len(clases) < 2:
        raise SystemExit(f"esperaba al menos 2 subcarpetas (clases) en {origen}, hay {clases}")
    salida: list[tuple[str, bytes]] = []
    for clase in clases:
        archivos = sorted(f for f in (origen / clase).iterdir() if f.suffix.lower() in EXTENSIONES)
        rng.shuffle(archivos)
        elegidos = archivos[:por_clase]
        print(f"  {clase}: {len(elegidos)} de {len(archivos)}")
        salida += [(clase, f.read_bytes()) for f in elegidos]
    return salida


def _info_hf(dataset: str, config: str) -> dict:
    """`/info` devuelve dataset_info directo o indexado por config, según la versión del servidor."""
    d = json.load(urllib.request.urlopen(f"{SERVIDOR_HF}/info?dataset={dataset}&config={config}", timeout=30))
    info = d["dataset_info"]
    return info if "features" in info else info[config]


def desde_hf(dataset: str, config: str, split: str, por_clase: int, rng: random.Random) -> list[tuple[str, bytes]]:
    """Baja filas etiquetadas por la API pública de datasets-server (no hace falta cuenta)."""
    info = _info_hf(dataset, config)
    clases = info["features"]["label"]["names"]
    total = info["splits"][split]["num_examples"]
    print(f"  {dataset} · {split}: {total} filas · clases {clases}")

    indices = list(range(total))
    rng.shuffle(indices)
    por_pagina = 100
    juntados: dict[str, list[bytes]] = {c: [] for c in clases}
    # Recorre páginas al azar hasta completar la cuota de cada clase.
    paginas = list(range(0, total, por_pagina))
    rng.shuffle(paginas)
    for offset in paginas:
        if all(len(v) >= por_clase for v in juntados.values()):
            break
        url = f"{SERVIDOR_HF}/rows?dataset={dataset}&config={config}&split={split}&offset={offset}&length={por_pagina}"
        for fila in json.load(urllib.request.urlopen(url, timeout=60))["rows"]:
            r = fila["row"]
            clase = clases[r["label"]] if isinstance(r["label"], int) else str(r["label"])
            if len(juntados[clase]) >= por_clase:
                continue
            src = r["image"]["src"] if isinstance(r.get("image"), dict) else None
            if not src:
                continue
            juntados[clase].append(urllib.request.urlopen(src, timeout=60).read())
        print("  " + " · ".join(f"{c}: {len(v)}" for c, v in juntados.items()))
    return [(c, b) for c, bs in juntados.items() for b in bs]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("origen", nargs="?", help="carpeta con una subcarpeta por clase")
    p.add_argument("--hf", help="dataset de Hugging Face, p. ej. hf-vision/chest-xray-pneumonia")
    p.add_argument("--config", default="default")
    p.add_argument("--split", default="test")
    p.add_argument("--salida", required=True, help="carpeta destino, p. ej. ./tmp/torax-rx/v1")
    p.add_argument("--por-clase", type=int, default=100)
    p.add_argument("--conjunto", default=None, help="tipo de estudio; por defecto, la carpeta padre de --salida")
    p.add_argument("--version", default=None, help="por defecto, el nombre de la carpeta de --salida")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--criterios", default=None)
    p.add_argument("--sin-optimizar", action="store_true", help="PNG sin compresión adicional; mismos píxeles")
    a = p.parse_args()
    if not a.origen and not a.hf:
        raise SystemExit("pasá una carpeta o --hf <dataset>")

    salida = Path(a.salida)
    conjunto = a.conjunto or salida.parent.name
    version = a.version or salida.name
    rng = random.Random(a.semilla)

    crudos = desde_hf(a.hf, a.config, a.split, a.por_clase, rng) if a.hf else desde_carpeta(Path(a.origen), a.por_clase, rng)
    if not crudos:
        raise SystemExit("no se juntó ningún caso")

    casos_dir = salida / "casos"
    casos_dir.mkdir(parents=True, exist_ok=True)
    verdad: list[dict] = []
    for clase, datos in crudos:
        nombre = f"{uuid.uuid4()}.png"            # nombre opaco: nada que insinúe el diagnóstico
        with Image.open(io.BytesIO(datos)) as img:
            img.convert("RGB").save(casos_dir / nombre, format="PNG", optimize=not a.sin_optimizar)
        verdad.append({"caso": nombre, "etiqueta": clase})

    rng.shuffle(verdad)                            # que el orden tampoco delate la clase
    with open(salida / "verdad.jsonl", "w", encoding="utf-8") as f:
        for linea in verdad:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")

    h = hashlib.sha256()
    for nombre in sorted(v["caso"] for v in verdad):
        h.update(hashlib.sha256((casos_dir / nombre).read_bytes()).hexdigest().encode())
    origen_txt = f"{a.hf} ({a.split})" if a.hf else Path(a.origen).name
    manifiesto = {
        "conjunto": conjunto,
        "version": version,
        "casos": len(verdad),
        "congelado_en": date.today().isoformat(),
        "etiquetas": sorted({v["etiqueta"] for v in verdad}),
        "criterios": a.criterios or f"{origen_txt}: hasta {a.por_clase} por clase, PNG RGB, semilla {a.semilla}",
        "hash": f"sha256:{h.hexdigest()}",
        "origen": a.hf or str(a.origen),
        "split": a.split if a.hf else None,
        "semilla": a.semilla,
    }
    (salida / "manifiesto.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(f"listo: {len(verdad)} casos en {salida} · hash {manifiesto['hash'][:19]}…")
    print(f"subir a: s3://<bucket-evaluacion>/{conjunto}/{version}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
