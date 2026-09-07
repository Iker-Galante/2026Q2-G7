import type { Modelo } from "../api/tipos";
import { etiquetaModelo } from "../utilidades/formato";

interface Props {
  modelos: Modelo[];
  seleccionadoId: string | null;
  cargando: boolean;
  deshabilitado?: boolean;
  onSeleccionar: (id: string) => void;
}

/** Lista desplegable de modelos publicados. */
export default function SelectorModelo({
  modelos,
  seleccionadoId,
  cargando,
  deshabilitado = false,
  onSeleccionar,
}: Props) {
  if (modelos.length === 0) {
    return (
      <p className="vacio">
        {cargando ? "Cargando modelos…" : "Todavía no hay modelos publicados. Publicá uno más abajo."}
      </p>
    );
  }

  return (
    <label className="campo">
      <span className="campo-etiqueta">Modelo publicado</span>
      <select
        value={seleccionadoId ?? ""}
        disabled={deshabilitado}
        onChange={(e) => onSeleccionar(e.target.value)}
      >
        {seleccionadoId === null && <option value="">Elegí un modelo…</option>}
        {modelos.map((m) => (
          <option key={m.id} value={m.id}>
            {etiquetaModelo(m)}
          </option>
        ))}
      </select>
    </label>
  );
}
