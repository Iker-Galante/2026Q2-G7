"""El contrato de un modelo: lo que declara `modelo.json`.

Este archivo NO importa numpy ni onnxruntime a propósito: el backend lo copia
tal cual en `backend/app/dominio/contrato.py` para validar al publicar sin
traer dependencias pesadas. Un test compara las dos copias byte a byte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LAYOUTS = ("NCHW", "NHWC")
ESPACIOS_COLOR = ("RGB", "L", "gris_replicado")
REDIMENSIONES = ("estirar", "recortar_centro")
TIPOS_SALIDA = ("logits", "probabilidades", "logit_sigmoide")
TAREAS = ("clasificacion",)


class ContratoInvalido(ValueError):
    """`modelo.json` no cumple el contrato. El mensaje dice qué campo."""


@dataclass(frozen=True)
class EspecEntrada:
    nombre: str | None          # nombre del tensor; None = el único de entrada del grafo
    layout: str                 # NCHW | NHWC
    forma: tuple[int, ...]      # con batch 1, p. ej. (1, 3, 224, 224)
    dtype: str                  # float32
    espacio_color: str          # RGB | L | gris_replicado
    redimension: str            # estirar | recortar_centro
    escala: float               # se divide el píxel por esto
    media: tuple[float, ...] | None
    desvio: tuple[float, ...] | None

    @property
    def alto(self) -> int:
        return self.forma[1] if self.layout == "NHWC" else self.forma[2]

    @property
    def ancho(self) -> int:
        return self.forma[2] if self.layout == "NHWC" else self.forma[3]

    @property
    def canales(self) -> int:
        return self.forma[3] if self.layout == "NHWC" else self.forma[1]


@dataclass(frozen=True)
class EspecSalida:
    nombre: str | None          # None = la única salida del grafo
    tipo: str                   # logits | probabilidades | logit_sigmoide
    etiquetas: tuple[str, ...]
    positiva: str | None        # etiqueta positiva, para métricas binarias
    umbral: float = 0.5         # solo para logit_sigmoide


@dataclass(frozen=True)
class ContratoModelo:
    nombre: str
    version: str
    tipo_estudio: str
    tarea: str
    entrada: EspecEntrada
    salida: EspecSalida
    origen: str | None = None
    crudo: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def es_binario(self) -> bool:
        return len(self.salida.etiquetas) == 2 and self.salida.positiva is not None

    @staticmethod
    def desde_json(d: dict[str, Any]) -> "ContratoModelo":
        if not isinstance(d, dict):
            raise ContratoInvalido("modelo.json tiene que ser un objeto JSON")
        for campo in ("nombre", "version", "tipo_estudio", "tarea", "entrada", "salida"):
            if campo not in d:
                raise ContratoInvalido(f"falta el campo obligatorio '{campo}'")
        if d["tarea"] not in TAREAS:
            raise ContratoInvalido(f"tarea '{d['tarea']}' no soportada; opciones: {TAREAS}")
        entrada = _parsear_entrada(d["entrada"])
        salida = _parsear_salida(d["salida"])
        return ContratoModelo(
            nombre=_texto(d, "nombre"),
            version=_texto(d, "version"),
            tipo_estudio=_texto(d, "tipo_estudio"),
            tarea=d["tarea"],
            entrada=entrada,
            salida=salida,
            origen=d.get("origen"),
            crudo=d,
        )


def _texto(d: dict[str, Any], campo: str) -> str:
    valor = d.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ContratoInvalido(f"'{campo}' tiene que ser un texto no vacío")
    return valor.strip()


def _parsear_entrada(e: Any) -> EspecEntrada:
    if not isinstance(e, dict):
        raise ContratoInvalido("'entrada' tiene que ser un objeto")
    layout = e.get("layout", "NCHW")
    if layout not in LAYOUTS:
        raise ContratoInvalido(f"entrada.layout '{layout}' inválido; opciones: {LAYOUTS}")
    forma = e.get("forma")
    if not isinstance(forma, list) or len(forma) != 4 or not all(isinstance(x, int) and x > 0 for x in forma):
        raise ContratoInvalido("entrada.forma tiene que ser una lista de 4 enteros positivos")
    if forma[0] != 1:
        raise ContratoInvalido("entrada.forma[0] (batch) tiene que ser 1")
    canales = forma[3] if layout == "NHWC" else forma[1]
    espacio = e.get("espacio_color", "RGB")
    if espacio not in ESPACIOS_COLOR:
        raise ContratoInvalido(f"entrada.espacio_color '{espacio}' inválido; opciones: {ESPACIOS_COLOR}")
    canales_esperados = 1 if espacio == "L" else 3
    if canales != canales_esperados:
        raise ContratoInvalido(
            f"entrada.espacio_color '{espacio}' implica {canales_esperados} canal(es) pero forma declara {canales}"
        )
    redimension = e.get("redimension", "estirar")
    if redimension not in REDIMENSIONES:
        raise ContratoInvalido(f"entrada.redimension '{redimension}' inválida; opciones: {REDIMENSIONES}")
    dtype = e.get("dtype", "float32")
    if dtype != "float32":
        raise ContratoInvalido("entrada.dtype: solo se soporta float32")
    escala = e.get("escala", 255)
    if not isinstance(escala, (int, float)) or escala <= 0:
        raise ContratoInvalido("entrada.escala tiene que ser un número positivo")
    media = _lista_float(e.get("media"), "entrada.media", canales)
    desvio = _lista_float(e.get("desvio"), "entrada.desvio", canales)
    if (media is None) != (desvio is None):
        raise ContratoInvalido("entrada.media y entrada.desvio van juntos: los dos o ninguno")
    if desvio is not None and any(x == 0 for x in desvio):
        raise ContratoInvalido("entrada.desvio no puede contener ceros")
    nombre = e.get("nombre")
    if nombre is not None and (not isinstance(nombre, str) or not nombre):
        raise ContratoInvalido("entrada.nombre tiene que ser un texto o null")
    return EspecEntrada(
        nombre=nombre,
        layout=layout,
        forma=tuple(forma),
        dtype=dtype,
        espacio_color=espacio,
        redimension=redimension,
        escala=float(escala),
        media=media,
        desvio=desvio,
    )


def _lista_float(valor: Any, campo: str, canales: int) -> tuple[float, ...] | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return tuple(float(valor) for _ in range(canales))
    if not isinstance(valor, list) or not all(isinstance(x, (int, float)) for x in valor):
        raise ContratoInvalido(f"{campo} tiene que ser un número, una lista de números o null")
    if len(valor) != canales:
        raise ContratoInvalido(f"{campo} tiene {len(valor)} valores pero la entrada tiene {canales} canales")
    return tuple(float(x) for x in valor)


def _parsear_salida(s: Any) -> EspecSalida:
    if not isinstance(s, dict):
        raise ContratoInvalido("'salida' tiene que ser un objeto")
    tipo = s.get("tipo")
    if tipo not in TIPOS_SALIDA:
        raise ContratoInvalido(f"salida.tipo '{tipo}' inválido; opciones: {TIPOS_SALIDA}")
    etiquetas = s.get("etiquetas")
    if not isinstance(etiquetas, list) or len(etiquetas) < 2 or not all(isinstance(x, str) and x for x in etiquetas):
        raise ContratoInvalido("salida.etiquetas tiene que ser una lista de al menos 2 textos")
    if len(set(etiquetas)) != len(etiquetas):
        raise ContratoInvalido("salida.etiquetas tiene repetidas")
    if tipo == "logit_sigmoide" and len(etiquetas) != 2:
        raise ContratoInvalido("salida.tipo logit_sigmoide requiere exactamente 2 etiquetas")
    positiva = s.get("positiva")
    if positiva is not None and positiva not in etiquetas:
        raise ContratoInvalido("salida.positiva tiene que ser una de salida.etiquetas")
    if tipo == "logit_sigmoide" and positiva is None:
        raise ContratoInvalido("salida.tipo logit_sigmoide requiere salida.positiva")
    umbral = s.get("umbral", 0.5)
    if not isinstance(umbral, (int, float)) or not 0 < umbral < 1:
        raise ContratoInvalido("salida.umbral tiene que estar entre 0 y 1")
    nombre = s.get("nombre")
    if nombre is not None and (not isinstance(nombre, str) or not nombre):
        raise ContratoInvalido("salida.nombre tiene que ser un texto o null")
    return EspecSalida(
        nombre=nombre,
        tipo=tipo,
        etiquetas=tuple(etiquetas),
        positiva=positiva,
        umbral=float(umbral),
    )
