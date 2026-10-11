import type { EstadoEvaluacion, Modelo } from "../api/tipos";
import { fechaLocal, porcentaje } from "../utilidades/formato";

interface Props {
  modelos: Modelo[];
  seleccionadoId: string | null;
  cargando: boolean;
  onSeleccionar: (id: string) => void;
}

function Estado({ estado }: { estado: EstadoEvaluacion }) {
  if (estado === "ok") return <span className="pastilla ok">evaluado</span>;
  if (estado === "error") return <span className="pastilla mal">error</span>;
  if (estado === "en_curso") {
    return (
      <span className="pastilla activa">
        <span className="spinner" aria-hidden="true" /> evaluando
      </span>
    );
  }
  return <span className="pastilla">pendiente</span>;
}

/** Mejor accuracy por tipo de estudio, solo si hay con qué comparar. */
function lideres(modelos: Modelo[]): Set<string> {
  const porTipo = new Map<string, Modelo[]>();
  for (const m of modelos) {
    if (m.estado_evaluacion !== "ok" || m.accuracy === null) continue;
    const lista = porTipo.get(m.tipo_estudio) ?? [];
    lista.push(m);
    porTipo.set(m.tipo_estudio, lista);
  }
  const ids = new Set<string>();
  for (const lista of porTipo.values()) {
    if (lista.length < 2) continue;
    const mejor = lista.reduce((a, b) => ((b.accuracy ?? 0) > (a.accuracy ?? 0) ? b : a));
    ids.add(mejor.id);
  }
  return ids;
}

function casosDe(m: Modelo): number | null {
  const n = m.metricas?.n_casos;
  if (typeof n === "number" && Number.isFinite(n)) return n;
  return m.manifiesto?.casos ?? null;
}

/** Todos los modelos publicados, medidos contra el mismo conjunto. */
export default function CatalogoModelos({ modelos, seleccionadoId, cargando, onSeleccionar }: Props) {
  if (modelos.length === 0) {
    return (
      <p className="vacio">
        {cargando ? "Cargando el catálogo…" : "El catálogo está vacío: todavía no se publicó ningún modelo."}
      </p>
    );
  }

  const mejores = lideres(modelos);

  return (
    <div className="tabla-scroll">
      <table className="catalogo">
        <thead>
          <tr>
            <th scope="col">Modelo</th>
            <th scope="col">Tipo de estudio</th>
            <th scope="col">Evaluación</th>
            <th scope="col">Accuracy</th>
            <th scope="col">Casos</th>
            <th scope="col">Conjunto</th>
            <th scope="col">Medido</th>
          </tr>
        </thead>
        <tbody>
          {modelos.map((m) => {
            const casos = casosDe(m);
            const ancho = m.accuracy !== null ? Math.max(0, Math.min(100, m.accuracy * 100)) : 0;
            return (
              <tr key={m.id} className={m.id === seleccionadoId ? "elegida" : undefined}>
                <td>
                  <button type="button" className="enlace" onClick={() => onSeleccionar(m.id)}>
                    {m.nombre}
                  </button>{" "}
                  <span className="version">v{m.version}</span>
                  {mejores.has(m.id) && (
                    <span className="pastilla mejor" title={`Mejor accuracy de ${m.tipo_estudio}`}>
                      mejor
                    </span>
                  )}
                </td>
                <td>
                  <span className="chip">{m.tipo_estudio}</span>
                </td>
                <td>
                  <Estado estado={m.estado_evaluacion} />
                </td>
                <td className="num">
                  {m.accuracy !== null ? (
                    <span className="celda-accuracy">
                      {porcentaje(m.accuracy)}
                      <span className="micro-barra" aria-hidden="true">
                        <span style={{ width: `${ancho}%` }} />
                      </span>
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="num">{casos ?? "—"}</td>
                <td className="num">
                  {m.conjunto ? `${m.conjunto}${m.conjunto_version ? ` ${m.conjunto_version}` : ""}` : "—"}
                </td>
                <td className="num">{m.evaluado_en ? fechaLocal(m.evaluado_en) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
