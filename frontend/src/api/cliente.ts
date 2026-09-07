import type { CuerpoError } from "./tipos";

const BASE = "/api";

/**
 * Error de la API. `status` es el HTTP, `error` el código que manda el backend
 * y `detalle` el texto legible para mostrar en pantalla.
 */
export class ErrorApi extends Error {
  readonly status: number;
  readonly error: string;
  readonly detalle: string;

  constructor(status: number, error: string, detalle: string) {
    super(detalle);
    this.name = "ErrorApi";
    this.status = status;
    this.error = error;
    this.detalle = detalle;
  }
}

function esCuerpoError(valor: unknown): valor is CuerpoError {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return typeof v.error === "string" && typeof v.detalle === "string";
}

async function leerError(respuesta: Response): Promise<ErrorApi> {
  let cuerpo: unknown = null;
  try {
    cuerpo = await respuesta.json();
  } catch {
    // Sin cuerpo JSON (p. ej. un 502 del balanceador): usamos el status.
  }
  if (esCuerpoError(cuerpo)) {
    return new ErrorApi(respuesta.status, cuerpo.error, cuerpo.detalle);
  }
  return new ErrorApi(
    respuesta.status,
    `http_${respuesta.status}`,
    `La API respondió ${respuesta.status} ${respuesta.statusText}`.trim(),
  );
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(BASE + ruta, init);
  } catch (e) {
    const motivo = e instanceof Error ? e.message : String(e);
    throw new ErrorApi(0, "red", `No se pudo conectar con la API (${motivo})`);
  }
  if (!respuesta.ok) throw await leerError(respuesta);
  // 204 sin cuerpo: devolvemos undefined tipado como T.
  if (respuesta.status === 204) return undefined as unknown as T;
  return (await respuesta.json()) as T;
}

export function get<T>(ruta: string): Promise<T> {
  return pedir<T>(ruta, { headers: { Accept: "application/json" } });
}

export function post<T>(ruta: string, cuerpo: unknown): Promise<T> {
  return pedir<T>(ruta, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(cuerpo),
  });
}

/** Convierte cualquier excepción en un texto para mostrar. */
export function mensajeDeError(e: unknown): string {
  if (e instanceof ErrorApi) return e.detalle;
  if (e instanceof Error) return e.message;
  return String(e);
}
