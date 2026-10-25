import { post } from "./cliente";
import type { SolicitudInferencia, Trabajo } from "./tipos";

/** Encola una inferencia; vuelve un Trabajo en estado "pendiente" (202). */
export function encolar(solicitud: SolicitudInferencia): Promise<Trabajo> {
  return post<Trabajo>("/inferencias", solicitud);
}
