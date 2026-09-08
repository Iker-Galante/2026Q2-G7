import type { ModeloDisponible } from "../api/tipos";

interface Props {
  disponibles: ModeloDisponible[];
  cargando: boolean;
  publicando: boolean;
  /** "nombre@version" del que se está publicando, para el spinner de esa fila. */
  claveEnCurso: string | null;
  onPublicar: (nombre: string, version: string) => void;
}

export function clave(m: { nombre: string; version: string }): string {
  return `${m.nombre}@${m.version}`;
}

/** Los prefijos con modelo.json que hay en el bucket, con su botón de alta. */
export default function ListaDisponibles({
  disponibles,
  cargando,
  publicando,
  claveEnCurso,
  onPublicar,
}: Props) {
  if (disponibles.length === 0) {
    return (
      <p className="vacio">
        {cargando
          ? "Buscando modelos en el bucket…"
          : "No hay ningún prefijo con modelo.json en el bucket de modelos. Subí un modelo y su contrato para verlo acá."}
      </p>
    );
  }

  return (
    <ul className="filas">
      {disponibles.map((m) => {
        const esta = claveEnCurso === clave(m);
        return (
          <li key={clave(m)} className="fila">
            <div className="fila-identidad">
              <span className="fila-nombre">{m.nombre}</span>
              <span className="version">v{m.version}</span>
            </div>

            <div className="fila-datos">
              <span className="chip">{m.tipo_estudio}</span>
              <span className={m.publicado ? "pastilla ok" : "pastilla"}>
                {m.publicado ? "en el catálogo" : "sin publicar"}
              </span>
            </div>

            <div className="fila-accion">
              {esta && <span className="spinner" aria-hidden="true" />}
              <button
                type="button"
                className={m.publicado ? "secundario" : undefined}
                disabled={publicando}
                onClick={() => onPublicar(m.nombre, m.version)}
              >
                {esta ? "Publicando…" : m.publicado ? "Volver a publicar" : "Publicar"}
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
