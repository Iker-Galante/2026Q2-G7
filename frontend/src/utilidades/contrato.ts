// Lectura del modelo.json en el navegador. La validación de verdad la hace la
// API (dominio/contrato.py); acá solo miramos lo mínimo para poder armar el
// destino en el bucket y avisar temprano de lo obvio.

import type { ContratoModelo } from "../api/tipos";

const SEGMENTO = /^[A-Za-z0-9._-]+$/;

export interface LecturaContrato {
  contrato: ContratoModelo | null;
  nombre: string;
  version: string;
  /** "torax-rx · clasificacion · NORMAL, PNEUMONIA" cuando se pudo leer. */
  resumen: string | null;
  error: string | null;
}

const VACIA: LecturaContrato = {
  contrato: null,
  nombre: "",
  version: "",
  resumen: null,
  error: null,
};

function texto(objeto: Record<string, unknown>, campo: string): string {
  const valor = objeto[campo];
  return typeof valor === "string" ? valor.trim() : "";
}

function fallo(error: string): LecturaContrato {
  return { ...VACIA, error };
}

export function leerContrato(crudo: string): LecturaContrato {
  if (crudo.trim() === "") return VACIA;

  let valor: unknown;
  try {
    valor = JSON.parse(crudo);
  } catch (e) {
    return fallo(`No es JSON válido: ${e instanceof Error ? e.message : String(e)}`);
  }
  if (typeof valor !== "object" || valor === null || Array.isArray(valor)) {
    return fallo("El contrato tiene que ser un objeto JSON.");
  }

  const objeto = valor as Record<string, unknown>;
  const nombre = texto(objeto, "nombre");
  const version = texto(objeto, "version");
  if (!SEGMENTO.test(nombre)) {
    return fallo("«nombre» tiene que estar y solo puede llevar letras, números, punto, guion o guion bajo.");
  }
  if (!SEGMENTO.test(version)) {
    return fallo("«version» tiene que estar y solo puede llevar letras, números, punto, guion o guion bajo.");
  }

  const tipoEstudio = texto(objeto, "tipo_estudio");
  const tarea = texto(objeto, "tarea");
  if (tipoEstudio === "" || tarea === "") {
    return fallo("Faltan «tipo_estudio» o «tarea».");
  }
  if (typeof objeto.entrada !== "object" || objeto.entrada === null) {
    return fallo("Falta el objeto «entrada» (layout, forma, normalización).");
  }
  const salida = objeto.salida;
  if (typeof salida !== "object" || salida === null) {
    return fallo("Falta el objeto «salida» (tipo, etiquetas).");
  }
  const etiquetas = (salida as Record<string, unknown>).etiquetas;
  if (!Array.isArray(etiquetas) || etiquetas.length < 2 || !etiquetas.every((e) => typeof e === "string")) {
    return fallo("«salida.etiquetas» tiene que ser una lista de al menos dos textos.");
  }

  return {
    contrato: objeto,
    nombre,
    version,
    resumen: `${tipoEstudio} · ${tarea} · ${etiquetas.join(", ")}`,
    error: null,
  };
}

/** El contrato del modelo de la demo (specs §7), para arrancar de algo que funciona. */
export const PLANTILLA_CONTRATO = `{
  "nombre": "torax-rx-neumonia",
  "version": "1.0.0",
  "tipo_estudio": "torax-rx",
  "tarea": "clasificacion",
  "origen": "https://huggingface.co/Rhishamah/mediscan-pneumonia",
  "entrada": {
    "nombre": "input",
    "layout": "NCHW",
    "forma": [1, 3, 224, 224],
    "dtype": "float32",
    "espacio_color": "RGB",
    "redimension": "estirar",
    "escala": 255,
    "media": [0.485, 0.456, 0.406],
    "desvio": [0.229, 0.224, 0.225]
  },
  "salida": {
    "nombre": "output",
    "tipo": "logit_sigmoide",
    "etiquetas": ["NORMAL", "PNEUMONIA"],
    "positiva": "PNEUMONIA",
    "umbral": 0.5
  }
}
`;
