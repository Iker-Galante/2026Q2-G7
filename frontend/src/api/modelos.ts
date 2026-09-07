import { get, post } from "./cliente";
import type { Modelo, ModeloDisponible, SolicitudPublicar } from "./tipos";

/** Modelos presentes en el bucket, publicados o no. */
export function listarDisponibles(): Promise<ModeloDisponible[]> {
  return get<ModeloDisponible[]>("/modelos/disponibles");
}

/** Modelos publicados, del más nuevo al más viejo. */
export function listarPublicados(): Promise<Modelo[]> {
  return get<Modelo[]>("/modelos");
}

export function obtener(id: string): Promise<Modelo> {
  return get<Modelo>(`/modelos/${encodeURIComponent(id)}`);
}

/** Da de alta el modelo y dispara su evaluación (202). */
export function publicar(solicitud: SolicitudPublicar): Promise<Modelo> {
  return post<Modelo>("/modelos/publicar", solicitud);
}
