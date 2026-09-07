#!/usr/bin/env python3
"""Comprueba que el `modelo.json` describe de verdad al `modelo.onnx`.

Hace las dos cosas que hay que hacer antes de confiar en un contrato:
  1. lo carga con el motor real (nombres y formas de los tensores tienen que existir);
  2. lo corre sobre casos etiquetados y muestra la accuracy, con `--casos <carpeta>`
     (una carpeta preparada por preparar_conjunto.py) o `--hf <dataset>`.

  python tools/verificar_modelo.py ./tmp/modelo --hf hf-vision/chest-xray-pneumonia --n 30
  python tools/verificar_modelo.py ./tmp/modelo --casos ./tmp/torax-rx/v1
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ateneo_ml import ContratoModelo, Inferidor  # noqa: E402
from ateneo_ml.metricas import calcular_metricas  # noqa: E402
from ateneo_ml.motor import OnnxMotor  # noqa: E402


def casos_de_carpeta(base: Path, n: int) -> list[tuple[str, bytes, str]]:
    verdad = [json.loads(l) for l in (base / "verdad.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    random.Random(0).shuffle(verdad)
    return [(v["caso"], (base / "casos" / v["caso"]).read_bytes(), v["etiqueta"]) for v in verdad[:n]]


def casos_de_hf(dataset: str, config: str, split: str, n: int) -> list[tuple[str, bytes, str]]:
    """Muestreo balanceado por clase: reusa el mismo código que arma los conjuntos."""
    from preparar_conjunto import desde_hf

    crudos = desde_hf(dataset, config, split, max(1, n // 2), random.Random(0))
    return [(f"caso-{i}.png", datos, clase) for i, (clase, datos) in enumerate(crudos)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("carpeta", help="carpeta con modelo.onnx y modelo.json")
    p.add_argument("--casos", help="carpeta de un conjunto preparado")
    p.add_argument("--hf", help="dataset de Hugging Face")
    p.add_argument("--config", default="default")
    p.add_argument("--split", default="test")
    p.add_argument("--n", type=int, default=30)
    a = p.parse_args()

    base = Path(a.carpeta)
    contrato = ContratoModelo.desde_json(json.loads((base / "modelo.json").read_text(encoding="utf-8")))
    inferidor = Inferidor(contrato, OnnxMotor(str(base / "modelo.onnx"), contrato))
    print(f"contrato ok: {contrato.nombre} v{contrato.version} · {contrato.tipo_estudio} · {list(contrato.salida.etiquetas)}")

    if not a.casos and not a.hf:
        print("(sin casos: pasá --casos o --hf para medir la accuracy)")
        return 0

    casos = casos_de_carpeta(Path(a.casos), a.n) if a.casos else casos_de_hf(a.hf, a.config, a.split, a.n)
    verdades, predicciones, probas = [], [], []
    for nombre, datos, etiqueta in casos:
        pred = inferidor.inferir(datos, nombre)
        verdades.append(etiqueta)
        predicciones.append(pred.prediccion)
        if contrato.es_binario:
            probas.append(pred.probabilidad_de(contrato.salida.positiva))
    m = calcular_metricas(verdades, predicciones, contrato.salida.etiquetas,
                          prob_positiva=probas if contrato.es_binario else None,
                          positiva=contrato.salida.positiva if contrato.es_binario else None)
    print(f"casos: {m['n_casos']} · accuracy: {m['accuracy']}")
    for k in ("sensibilidad", "especificidad", "auc", "f1_macro"):
        if k in m:
            print(f"  {k}: {m[k]}")
    print(f"  matriz: {m['matriz_confusion']['etiquetas']} → {m['matriz_confusion']['valores']}")
    if m["accuracy"] < 0.6:
        print("\n⚠ accuracy muy baja: revisá media/desvío, espacio de color o el orden de las etiquetas en modelo.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
