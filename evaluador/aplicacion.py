"""EvaluarModelo: el caso de uso que corre en eval-1.

Los casos nunca salen de la subred; lo que sale es un número.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from ateneo_ml import ContratoInvalido, ContratoModelo, Inferidor
from ateneo_ml.errores import ErrorAteneoML
from ateneo_ml.metricas import calcular_metricas
from ateneo_ml.motor import OnnxMotor

from .puertos import (
    ColaModelos, Conjunto, ConjuntoInvalido, DescargadorModelo, LectorConjunto, ModeloPendiente,
    ResultadoEvaluacion,
)

log = logging.getLogger(__name__)


class EvaluarModelo:
    def __init__(self, cola: ColaModelos, conjuntos: LectorConjunto, descargador: DescargadorModelo,
                 directorio_trabajo: str, max_fraccion_errores: float, hilos: int | None = None):
        self._cola = cola
        self._conjuntos = conjuntos
        self._descargador = descargador
        self._trabajo = Path(directorio_trabajo)
        self._max_errores = max_fraccion_errores
        self._hilos = hilos

    def ejecutar(self, modelo: ModeloPendiente) -> None:
        carpeta = self._trabajo / f"{modelo.nombre}-{modelo.version}"
        try:
            log.info("evaluando %s v%s (%s)", modelo.nombre, modelo.version, modelo.id)
            resultado = self._evaluar(modelo, carpeta)
            self._cola.terminar_ok(modelo, resultado)
            log.info("evaluación ok %s v%s accuracy=%s casos=%s",
                     modelo.nombre, modelo.version, resultado.metricas["accuracy"], resultado.metricas["n_casos"])
        except (ContratoInvalido, ConjuntoInvalido, ErrorAteneoML) as e:
            log.error("evaluación falló %s v%s: %s", modelo.nombre, modelo.version, e)
            self._cola.terminar_error(modelo, str(e))
        except Exception as e:                       # noqa: BLE001 — una evaluación rota no tira el proceso
            log.exception("evaluación falló de forma inesperada %s v%s", modelo.nombre, modelo.version)
            self._cola.terminar_error(modelo, f"{e.__class__.__name__}: {e}")
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    def _evaluar(self, modelo: ModeloPendiente, carpeta: Path) -> ResultadoEvaluacion:
        inicio = time.perf_counter()

        # 1. el modelo candidato
        ruta = self._descargador.descargar(modelo.s3_prefix, carpeta)
        contrato = ContratoModelo.desde_json(json.loads((ruta / "modelo.json").read_text(encoding="utf-8")))
        if contrato.tipo_estudio != modelo.tipo_estudio:
            raise ContratoInvalido(f"modelo.json dice tipo_estudio {contrato.tipo_estudio} y el catálogo {modelo.tipo_estudio}")
        inferidor = Inferidor(contrato, OnnxMotor(str(ruta / "modelo.onnx"), contrato, hilos=self._hilos))

        # 2. el conjunto reservado, en su última versión
        version = self._conjuntos.ultima_version(modelo.tipo_estudio)
        if version is None:
            raise ConjuntoInvalido(f"no hay ningún conjunto de evaluación para '{modelo.tipo_estudio}'")
        conjunto = self._conjuntos.cargar(modelo.tipo_estudio, version)
        _validar_conjunto(conjunto, contrato, self._conjuntos)

        # 3. inferir cada caso
        verdades: list[str] = []
        predicciones: list[str] = []
        prob_positiva: list[float] = []
        errores = 0
        for i, caso in enumerate(conjunto.casos, start=1):
            try:
                datos = self._conjuntos.leer_caso(conjunto, caso)
                pred = inferidor.inferir(datos, caso.nombre)
            except ErrorAteneoML as e:
                errores += 1
                log.warning("caso ilegible %s: %s", caso.nombre, e)
                continue
            verdades.append(caso.etiqueta)
            predicciones.append(pred.prediccion)
            if contrato.es_binario:
                prob_positiva.append(pred.probabilidad_de(contrato.salida.positiva))  # type: ignore[arg-type]
            if i % 25 == 0 or i == len(conjunto.casos):
                log.info("progreso %s/%s", i, len(conjunto.casos))

        if errores > self._max_errores * len(conjunto.casos):
            raise ConjuntoInvalido(f"{errores} de {len(conjunto.casos)} casos no se pudieron procesar")

        # 4. métricas
        metricas = calcular_metricas(
            verdades, predicciones, contrato.salida.etiquetas,
            prob_positiva=prob_positiva if contrato.es_binario else None,
            positiva=contrato.salida.positiva if contrato.es_binario else None,
        )
        metricas["casos_con_error"] = errores
        metricas["duracion_s"] = round(time.perf_counter() - inicio, 1)
        return ResultadoEvaluacion(
            metricas=metricas, conjunto=conjunto.tipo_estudio, conjunto_version=conjunto.version,
            manifiesto=conjunto.manifiesto, terminado=datetime.now(timezone.utc),
        )


def _validar_conjunto(conjunto: Conjunto, contrato: ContratoModelo, lector: LectorConjunto) -> None:
    m = conjunto.manifiesto
    if not conjunto.casos:
        raise ConjuntoInvalido("verdad.jsonl está vacío")
    if "casos" in m and int(m["casos"]) != len(conjunto.casos):
        raise ConjuntoInvalido(f"manifiesto.json declara {m['casos']} casos y verdad.jsonl tiene {len(conjunto.casos)}")
    en_bucket = set(lector.listar_casos(conjunto.tipo_estudio, conjunto.version))
    faltan = [c.nombre for c in conjunto.casos if c.nombre not in en_bucket]
    if faltan:
        raise ConjuntoInvalido(f"{len(faltan)} casos de verdad.jsonl no están en casos/ (p. ej. {faltan[0]})")
    desconocidas = sorted({c.etiqueta for c in conjunto.casos} - set(contrato.salida.etiquetas))
    if desconocidas:
        raise ConjuntoInvalido(f"etiquetas del conjunto que el modelo no conoce: {desconocidas}")
