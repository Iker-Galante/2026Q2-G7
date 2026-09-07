import type { Trabajo } from "../api/tipos";
import { duracion, idCorto, porcentaje } from "../utilidades/formato";

interface Props {
  trabajo: Trabajo;
}

/** Predicción del modelo con las probabilidades por etiqueta. */
export default function ResultadoInferencia({ trabajo }: Props) {
  if (trabajo.estado === "error") {
    return (
      <div className="caja-error" role="alert">
        <strong>La inferencia falló.</strong>
        <p>{trabajo.error ?? "Sin detalle."}</p>
      </div>
    );
  }

  if (trabajo.estado !== "ok" || trabajo.resultado === null) return null;

  const { prediccion, probabilidades } = trabajo.resultado;
  const barras = Object.entries(probabilidades).sort(([, a], [, b]) => b - a);

  return (
    <section className="resultado" aria-live="polite">
      <div className="prediccion">
        <span className="prediccion-nombre">Predicción</span>
        <span className="prediccion-valor">{prediccion}</span>
      </div>

      <ul className="barras">
        {barras.map(([etiqueta, p]) => {
          const ancho = Math.max(0, Math.min(100, p * 100));
          return (
            <li key={etiqueta} className={etiqueta === prediccion ? "destacada" : undefined}>
              <span className="barra-etiqueta">{etiqueta}</span>
              <span className="barra-pista">
                <span className="barra-relleno" style={{ width: `${ancho}%` }} />
              </span>
              <span className="barra-valor">{porcentaje(p)}</span>
            </li>
          );
        })}
      </ul>

      <dl className="detalles">
        {trabajo.duracion_ms !== null && (
          <div>
            <dt>Duración</dt>
            <dd>{duracion(trabajo.duracion_ms)}</dd>
          </div>
        )}
        {trabajo.worker_id && (
          <div>
            <dt>Worker</dt>
            <dd>
              <code>{trabajo.worker_id}</code>
            </dd>
          </div>
        )}
        <div>
          <dt>Trabajo</dt>
          <dd>
            <code title={trabajo.id}>{idCorto(trabajo.id)}</code>
          </dd>
        </div>
      </dl>
    </section>
  );
}
