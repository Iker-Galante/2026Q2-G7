import { post } from "./cliente";
import type { EstudioCreado, SolicitudEstudio } from "./tipos";

/** Registra el estudio y devuelve el presigned POST para subir el archivo. */
export function crear(solicitud: SolicitudEstudio): Promise<EstudioCreado> {
  return post<EstudioCreado>("/estudios", solicitud);
}
