"""Modelos: caché en EFS (compartida entre workers) + LRU de sesiones en memoria.

Si el modelo no está en EFS, se baja de S3 a un directorio temporal y se mueve
con `rename` atómico: dos workers bajando el mismo modelo no se pisan, y una
instancia nueva ya lo encuentra montado.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

from botocore.exceptions import ClientError

from ateneo_ml import ContratoInvalido, ContratoModelo, Inferidor
from ateneo_ml.motor import OnnxMotor

from ..puertos import NoEncontrado, RefModelo

log = logging.getLogger(__name__)

ARCHIVOS = ("modelo.onnx", "modelo.json")


class ProveedorEfsS3:
    def __init__(self, cliente_s3, modelos_dir: str, cache_sesiones: int = 4, hilos: int | None = None):
        self._s3 = cliente_s3
        self._raiz = Path(modelos_dir)
        self._max = cache_sesiones
        self._hilos = hilos
        self._cache: OrderedDict[tuple[str, str], Inferidor] = OrderedDict()
        self._lock = threading.Lock()

    def obtener(self, ref: RefModelo) -> Inferidor:
        clave = (ref.nombre, ref.version)
        with self._lock:
            if clave in self._cache:
                self._cache.move_to_end(clave)
                return self._cache[clave]
        carpeta = self._asegurar_en_disco(ref)
        inferidor = self._cargar(carpeta)
        with self._lock:
            self._cache[clave] = inferidor
            while len(self._cache) > self._max:
                viejo, _ = self._cache.popitem(last=False)
                log.info("modelo descargado de memoria: %s", viejo)
        return inferidor

    # ---- disco ----

    def _asegurar_en_disco(self, ref: RefModelo) -> Path:
        destino = self._raiz / ref.nombre / ref.version
        if all((destino / a).is_file() for a in ARCHIVOS):
            return destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = Path(tempfile.mkdtemp(prefix=f".{ref.version}-", dir=destino.parent))
        try:
            for archivo in ARCHIVOS:
                key = f"{ref.prefix}{archivo}"
                log.info("bajando s3://%s/%s", ref.bucket, key)
                try:
                    self._s3.download_file(ref.bucket, key, str(temporal / archivo))
                except ClientError as e:
                    if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                        raise NoEncontrado(f"no existe s3://{ref.bucket}/{key}") from e
                    raise
            try:
                os.rename(temporal, destino)          # atómico dentro del mismo sistema de archivos
            except OSError:
                if all((destino / a).is_file() for a in ARCHIVOS):
                    shutil.rmtree(temporal, ignore_errors=True)   # otro worker llegó primero
                else:
                    raise
        except BaseException:
            shutil.rmtree(temporal, ignore_errors=True)
            raise
        return destino

    def _cargar(self, carpeta: Path) -> Inferidor:
        try:
            contrato = ContratoModelo.desde_json(json.loads((carpeta / "modelo.json").read_text(encoding="utf-8")))
        except (ContratoInvalido, ValueError) as e:
            raise ContratoInvalido(f"{carpeta / 'modelo.json'}: {e}") from e
        motor = OnnxMotor(str(carpeta / "modelo.onnx"), contrato, hilos=self._hilos)
        log.info("modelo cargado: %s v%s desde %s", contrato.nombre, contrato.version, carpeta)
        return Inferidor(contrato, motor)
