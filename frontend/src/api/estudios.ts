import { ErrorApi, post } from "./cliente";
import type { EstudioCreado, SolicitudEstudio, SubidaPresignada } from "./tipos";

/** Registra el estudio y devuelve el presigned POST para subir el archivo. */
export function crear(solicitud: SolicitudEstudio): Promise<EstudioCreado> {
  return post<EstudioCreado>("/estudios", solicitud);
}

/**
 * Sube el archivo a S3 con el presigned POST: primero todos los campos
 * firmados y el archivo al final bajo "file". No se fija Content-Type a mano:
 * el navegador arma el multipart con su propio boundary.
 */
export async function subirArchivoAS3(
  subida: SubidaPresignada,
  archivo: File,
): Promise<void> {
  const formData = new FormData();
  for (const [campo, valor] of Object.entries(subida.campos)) {
    formData.append(campo, valor);
  }
  formData.append("file", archivo, archivo.name);

  let respuesta: Response;
  try {
    respuesta = await fetch(subida.url, { method: "POST", body: formData });
  } catch (e) {
    const motivo = e instanceof Error ? e.message : String(e);
    throw new ErrorApi(0, "s3_red", `No se pudo subir la imagen a S3 (${motivo})`);
  }
  // S3 responde 204 (o 200/201 según success_action_status).
  if (!respuesta.ok) {
    throw new ErrorApi(
      respuesta.status,
      "s3_rechazo",
      `S3 rechazó la subida (${respuesta.status} ${respuesta.statusText})`.trim(),
    );
  }
}
