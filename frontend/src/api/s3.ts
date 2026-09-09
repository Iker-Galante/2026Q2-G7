import { ErrorApi } from "./cliente";
import type { SubidaPresignada } from "./tipos";

/**
 * Sube un archivo a S3 con un presigned POST: primero todos los campos
 * firmados y el archivo al final bajo "file". No se fija Content-Type a mano:
 * el navegador arma el multipart con su propio boundary.
 *
 * Va con XMLHttpRequest y no con fetch porque es el único que informa el
 * progreso de la subida, y un modelo pesa decenas de MB. Lo usan las dos
 * subidas del producto: la del estudio y la del ONNX.
 */
export function subirArchivoAS3(
  subida: SubidaPresignada,
  archivo: File,
  onProgreso?: (fraccion: number) => void,
): Promise<void> {
  const formData = new FormData();
  for (const [campo, valor] of Object.entries(subida.campos)) {
    formData.append(campo, valor);
  }
  formData.append("file", archivo, archivo.name);

  return new Promise((resolver, rechazar) => {
    const peticion = new XMLHttpRequest();
    peticion.open("POST", subida.url);

    peticion.upload.addEventListener("progress", (e) => {
      if (onProgreso && e.lengthComputable && e.total > 0) onProgreso(e.loaded / e.total);
    });

    peticion.addEventListener("load", () => {
      // S3 responde 204 (o 200/201 según success_action_status).
      if (peticion.status >= 200 && peticion.status < 300) {
        onProgreso?.(1);
        resolver();
        return;
      }
      rechazar(
        new ErrorApi(
          peticion.status,
          "s3_rechazo",
          `S3 rechazó la subida (${peticion.status} ${peticion.statusText})`.trim(),
        ),
      );
    });

    peticion.addEventListener("error", () =>
      rechazar(
        new ErrorApi(
          0,
          "s3_red",
          "No se pudo subir el archivo a S3: puede ser la red o el CORS del bucket.",
        ),
      ),
    );

    peticion.addEventListener("abort", () =>
      rechazar(new ErrorApi(0, "s3_cancelado", "La subida se canceló.")),
    );

    peticion.send(formData);
  });
}
