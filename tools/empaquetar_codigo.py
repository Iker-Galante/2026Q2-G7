"""Prepara solo la lista explícita de Terraform; copia bytes, incluidos binarios."""
import json
import shutil
import sys
from pathlib import Path


def preparar(raiz: Path, destino: Path, archivos: list[str]):
    raiz = raiz.resolve()
    for nombre in archivos:
        relativo = Path(nombre)
        origen = (raiz / relativo).resolve()
        if relativo.is_absolute() or ".." in relativo.parts or not origen.is_relative_to(raiz):
            raise ValueError("Ruta fuera del repositorio")
        objetivo = destino / relativo
        objetivo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, objetivo)


if __name__ == "__main__":
    consulta = json.load(sys.stdin)
    destino = Path(consulta["destino"])
    preparar(Path(consulta["raiz"]), destino, json.loads(consulta["archivos"]))
    print(json.dumps({"directorio": str(destino)}))
