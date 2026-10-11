import type { Modelo } from "../api/tipos";
import { Enlace } from "../enrutador";
import { porcentaje } from "../utilidades/formato";

interface Props {
  modelos: Modelo[];
  seleccionadoId: string | null;
  cargando: boolean;
  deshabilitado?: boolean;
  onSeleccionar: (id: string) => void;
}

function Medida({ modelo }: { modelo: Modelo }) {
  if (modelo.estado_evaluacion === "ok" && modelo.accuracy !== null) {
    return (
      <span className="opcion-medida">
        <span className="opcion-accuracy">{porcentaje(modelo.accuracy)}</span>
        <span className="opcion-medida-nombre">accuracy</span>
      </span>
    );
  }
  if (modelo.estado_evaluacion === "en_curso") {
    return (
      <span className="opcion-medida">
        <span className="pastilla activa">
          <span className="spinner" aria-hidden="true" /> evaluando
        </span>
      </span>
    );
  }
  if (modelo.estado_evaluacion === "error") {
    return (
      <span className="opcion-medida">
        <span className="pastilla mal">evaluación fallida</span>
      </span>
    );
  }
  return (
    <span className="opcion-medida">
      <span className="pastilla">sin evaluar</span>
    </span>
  );
}

/** Los modelos publicados como tarjetas, con la medida a la vista. */
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
        {cargando ? (
          "Cargando modelos…"
        ) : (
          <>
            Todavía no hay modelos publicados. <Enlace a="/publicar">Publicá el primero</Enlace> para
            poder consultar un estudio.
          </>
        )}
      </p>
    );
  }

  return (
    <fieldset className="opciones" disabled={deshabilitado}>
      <legend className="sr-solo">Modelo publicado</legend>
      {modelos.map((m) => {
        const elegido = m.id === seleccionadoId;
        return (
          <label key={m.id} className={elegido ? "opcion elegida" : "opcion"}>
            <input
              type="radio"
              name="modelo"
              value={m.id}
              checked={elegido}
              onChange={() => onSeleccionar(m.id)}
            />
            <span className="opcion-cuerpo">
              <span className="opcion-cabecera">
                <span className="opcion-nombre">{m.nombre}</span>
                <span className="version">v{m.version}</span>
              </span>
              <Medida modelo={m} />
              <span className="opcion-datos">
                <span className="chip">{m.tipo_estudio}</span>
                {m.etiquetas.length > 0 && <span className="suave">{m.etiquetas.join(" · ")}</span>}
              </span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
