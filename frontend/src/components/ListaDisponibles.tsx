import type { Modelo, ModeloDisponible } from "../api/tipos";
import { Enlace, rutaDeModelo } from "../enrutador";
import { porcentaje } from "../utilidades/formato";
import EstadoModelo from "./EstadoModelo";

interface Props {
  disponibles: ModeloDisponible[];
  /** Los publicados, para mostrar el estado de la evaluación de cada uno. */
  publicados: Modelo[];
  cargando: boolean;
  publicando: boolean;
  /** "nombre@version" del que se está publicando, para el spinner de esa fila. */
  claveEnCurso: string | null;
  onPublicar: (nombre: string, version: string) => void;
}

export function clave(m: { nombre: string; version: string }): string {
  return `${m.nombre}@${m.version}`;
}

/** Los modelos que hay en el bucket: su estado y la acción que corresponde. */
export default function ListaDisponibles({
  disponibles,
  publicados,
  cargando,
  publicando,
  claveEnCurso,
  onPublicar,
}: Props) {
  if (disponibles.length === 0) {
    return <p className="vacio chico">{cargando ? "Cargando…" : "Todavía no subiste ningún modelo."}</p>;
  }

  const porId = new Map(publicados.map((m) => [m.id, m]));

  return (
    <ul className="filas">
      {disponibles.map((d) => {
        const esta = claveEnCurso === clave(d);
        const modelo = d.modelo_id ? porId.get(d.modelo_id) : undefined;
        return (
          <li key={clave(d)} className="fila">
            <div className="fila-identidad">
              {modelo ? (
                <Enlace a={rutaDeModelo(modelo.id)} className="fila-nombre">
                  {d.nombre}
                </Enlace>
              ) : (
                <span className="fila-nombre">{d.nombre}</span>
              )}
              <span className="version">v{d.version}</span>
              <span className="fila-tipo">{d.tipo_estudio}</span>
            </div>

            <div className="fila-estado">
              {modelo ? (
                <>
                  <EstadoModelo estado={modelo.estado_evaluacion} />
                  {modelo.accuracy !== null && <span className="fila-accuracy">{porcentaje(modelo.accuracy)}</span>}
                </>
              ) : (
                <span className="pastilla">Sin publicar</span>
              )}
            </div>

            <button
              type="button"
              className="pildora pildora-borde chica"
              disabled={publicando}
              onClick={() => onPublicar(d.nombre, d.version)}
              title={d.publicado ? "Borra las métricas y lo vuelve a evaluar" : undefined}
            >
              {esta ? "Publicando…" : d.publicado ? "Reevaluar" : "Publicar"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
