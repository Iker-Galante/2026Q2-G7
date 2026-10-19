import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import { tamanoLegible } from "../utilidades/formato";

const TIPOS_PERMITIDOS = ["image/png", "image/jpeg"];
const TAMANO_MAXIMO = 20 * 1024 * 1024; // 20 MB, igual que MAX_BYTES_ESTUDIO en el backend

interface Props {
  archivo: File | null;
  tipoEstudio: string | null;
  deshabilitado?: boolean;
  onSeleccionar: (archivo: File) => void;
  onQuitar: () => void;
}

function validar(archivo: File): string | null {
  if (!TIPOS_PERMITIDOS.includes(archivo.type)) {
    return "Solo se aceptan imágenes PNG o JPEG.";
  }
  if (archivo.size > TAMANO_MAXIMO) {
    return `La imagen pesa ${tamanoLegible(archivo.size)}; el máximo es 20 MB.`;
  }
  return null;
}

/** Zona de arrastrar y soltar + selector de archivo, con vista previa local. */
export default function CargadorImagen({
  archivo,
  tipoEstudio,
  deshabilitado = false,
  onSeleccionar,
  onQuitar,
}: Props) {
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [vistaPrevia, setVistaPrevia] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  // URL local para la vista previa; se libera al cambiar de archivo o desmontar.
  useEffect(() => {
    if (archivo === null) {
      setVistaPrevia(null);
      return;
    }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  const recibir = (lista: FileList | null) => {
    if (deshabilitado) return;
    const elegido = lista?.[0];
    if (!elegido) return;
    const problema = validar(elegido);
    setMensaje(problema);
    if (problema === null) onSeleccionar(elegido);
  };

  const soltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    recibir(e.dataTransfer.files);
  };

  const abrirSelector = () => {
    if (!deshabilitado) entrada.current?.click();
  };

  return (
    <div className="cargador">
      <div
        className={`zona-soltar${arrastrando ? " activa" : ""}${deshabilitado ? " deshabilitada" : ""}`}
        role="button"
        tabIndex={deshabilitado ? -1 : 0}
        aria-disabled={deshabilitado}
        onClick={abrirSelector}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            abrirSelector();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!deshabilitado) setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={soltar}
      >
        {vistaPrevia && archivo ? (
          <img className="vista-previa" src={vistaPrevia} alt={`Vista previa de ${archivo.name}`} />
        ) : (
          <>
            <p>
              <strong>Arrastrá una imagen acá</strong> o hacé clic para elegirla.
            </p>
            <p className="suave">PNG o JPEG, hasta 20 MB.</p>
          </>
        )}
        <input
          ref={entrada}
          type="file"
          accept="image/png,image/jpeg"
          hidden
          disabled={deshabilitado}
          onChange={(e) => {
            recibir(e.target.files);
            // Permite volver a elegir el mismo archivo.
            e.target.value = "";
          }}
        />
      </div>

      {archivo && (
        <div className="archivo-info">
          <span className="archivo-nombre" title={archivo.name}>
            {archivo.name}
          </span>
          <span className="suave">{tamanoLegible(archivo.size)}</span>
          {tipoEstudio && <span className="chip">{tipoEstudio}</span>}
          <button type="button" className="pildora pildora-borde chica" onClick={onQuitar} disabled={deshabilitado}>
            Quitar
          </button>
        </div>
      )}

      {mensaje && (
        <div className="caja-error" role="alert">
          {mensaje}
        </div>
      )}
    </div>
  );
}
