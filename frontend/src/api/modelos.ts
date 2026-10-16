import { get, post } from "./cliente";
import type {
  Modelo, ModeloDisponible, SolicitudPublicar, SolicitudSubidaModelo, SubidaModeloCreada,
} from "./tipos";

/** Modelos presentes en el bucket, publicados o no. Es del publicador: pide token. */
export function listarDisponibles(): Promise<ModeloDisponible[]> {
  return get<ModeloDisponible[]>("/modelos/disponibles");
}

/**
 * El catálogo: modelos publicados, del más nuevo al más viejo. Cuelga de /publico porque
 * se ve sin ingresar, que es el único prefijo que API Gateway deja pasar sin token.
 */
export function listarPublicados(): Promise<Modelo[]> {
  return get<Modelo[]>("/publico/modelos");
}

/** La ficha de un modelo del catálogo; también pública. */
export function obtener(id: string): Promise<Modelo> {
  return get<Modelo>(`/publico/modelos/${encodeURIComponent(id)}`);
}

/**
 * Reserva el lugar del modelo en el bucket y devuelve el POST prefirmado para
 * mandarle el ONNX. El archivo no pasa por la API (201).
 */
export function crearSubida(solicitud: SolicitudSubidaModelo): Promise<SubidaModeloCreada> {
  return post<SubidaModeloCreada>("/modelos/subidas", solicitud);
}

/** Da de alta el modelo y dispara su evaluación (202). */
export function publicar(solicitud: SolicitudPublicar): Promise<Modelo> {
  return post<Modelo>("/modelos/publicar", solicitud);
}
