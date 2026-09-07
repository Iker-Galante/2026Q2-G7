import type { MatrizConfusion, Modelo } from "../api/tipos";
import { fechaLocal, hashCorto, numero, porcentaje } from "../utilidades/formato";

interface Props {
  modelo: Modelo;
}

type Metricas = Record<string, unknown>;

function leerNumero(metricas: Metricas | null, clave: string): number | null {
  const valor = metricas?.[clave];
  return typeof valor === "number" && Number.isFinite(valor) ? valor : null;
}

function esMatrizConfusion(valor: unknown): valor is MatrizConfusion {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    Array.isArray(v.etiquetas) &&
    v.etiquetas.every((e) => typeof e === "string") &&
    Array.isArray(v.valores) &&
    v.valores.every((fila) => Array.isArray(fila) && fila.every((n) => typeof n === "number"))
  );
}

interface DefinicionMetrica {
  clave: string;
  nombre: string;
  esPorcentaje: boolean;
}

interface MetricaConValor extends DefinicionMetrica {
  valor: number;
}

/** Métricas secundarias, en el orden en que se muestran. Solo se listan las presentes. */
const METRICAS_SECUNDARIAS: ReadonlyArray<DefinicionMetrica> = [
  { clave: "precision_macro", nombre: "Precisión (macro)", esPorcentaje: true },
  { clave: "sensibilidad_macro", nombre: "Sensibilidad (macro)", esPorcentaje: true },
  { clave: "f1_macro", nombre: "F1 (macro)", esPorcentaje: true },
  { clave: "sensibilidad", nombre: "Sensibilidad", esPorcentaje: true },
  { clave: "especificidad", nombre: "Especificidad", esPorcentaje: true },
  { clave: "precision", nombre: "Precisión", esPorcentaje: true },
  { clave: "f1", nombre: "F1", esPorcentaje: true },
  { clave: "auc", nombre: "AUC", esPorcentaje: false },
];

function TablaConfusion({ matriz }: { matriz: MatrizConfusion }) {
  return (
    <div className="tabla-scroll">
      <table className="matriz">
        <caption>Matriz de confusión (filas: real · columnas: predicho)</caption>
        <thead>
          <tr>
            <th scope="col" />
            {matriz.etiquetas.map((e) => (
              <th key={e} scope="col">
                {e}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matriz.valores.map((fila, i) => (
            <tr key={matriz.etiquetas[i] ?? i}>
              <th scope="row">{matriz.etiquetas[i] ?? `#${i}`}</th>
              {fila.map((n, j) => (
                <td key={j} className={i === j ? "diagonal" : undefined}>
                  {n}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Ficha del modelo elegido: estado de la evaluación y sus métricas. */
export default function TarjetaEvaluacion({ modelo }: Props) {
  const { metricas, manifiesto } = modelo;
  const nCasos = leerNumero(metricas, "n_casos") ?? manifiesto?.casos ?? null;
  const casosConError = leerNumero(metricas, "casos_con_error");
  const duracionS = leerNumero(metricas, "duracion_s");
  const matriz = metricas?.matriz_confusion;
  const secundarias: MetricaConValor[] = [];
  for (const definicion of METRICAS_SECUNDARIAS) {
    const valor = leerNumero(metricas, definicion.clave);
    if (valor !== null) secundarias.push({ ...definicion, valor });
  }

  return (
    <section className="tarjeta" aria-live="polite">
      <header className="tarjeta-cabecera">
        <h3>
          {modelo.nombre} <span className="suave">v{modelo.version}</span>
        </h3>
        <p className="suave">
          {modelo.tipo_estudio} · {modelo.tarea}
          {modelo.etiquetas.length > 0 && <> · {modelo.etiquetas.join(", ")}</>}
        </p>
      </header>

      {modelo.estado_evaluacion === "pendiente" && (
        <p className="estado-evaluacion">
          <span className="punto" /> Sin evaluar · En cola de evaluación…
        </p>
      )}

      {modelo.estado_evaluacion === "en_curso" && (
        <p className="estado-evaluacion">
          <span className="spinner" aria-hidden="true" /> Evaluando…
        </p>
      )}

      {modelo.estado_evaluacion === "error" && (
        <div className="caja-error" role="alert">
          <strong>La evaluación falló.</strong>
          <p>{modelo.error ?? "Sin detalle."}</p>
        </div>
      )}

      {modelo.estado_evaluacion === "ok" && (
        <>
          <div className="accuracy">
            <span className="accuracy-valor">
              {modelo.accuracy !== null ? porcentaje(modelo.accuracy) : "—"}
            </span>
            <span className="accuracy-nombre">accuracy</span>
          </div>

          {secundarias.length > 0 && (
            <dl className="metricas">
              {secundarias.map((m) => (
                <div key={m.clave}>
                  <dt>{m.nombre}</dt>
                  <dd>{m.esPorcentaje ? porcentaje(m.valor) : numero(m.valor)}</dd>
                </div>
              ))}
            </dl>
          )}

          {esMatrizConfusion(matriz) && <TablaConfusion matriz={matriz} />}
        </>
      )}

      <dl className="detalles">
        {nCasos !== null && (
          <div>
            <dt>Casos</dt>
            <dd>
              {nCasos}
              {casosConError !== null && casosConError > 0 && (
                <span className="suave"> · {casosConError} con error</span>
              )}
            </dd>
          </div>
        )}
        {modelo.conjunto && (
          <div>
            <dt>Conjunto</dt>
            <dd>
              {modelo.conjunto}
              {modelo.conjunto_version && ` v${modelo.conjunto_version}`}
            </dd>
          </div>
        )}
        {manifiesto?.hash && (
          <div>
            <dt>Manifiesto</dt>
            <dd>
              <code title={manifiesto.hash}>{hashCorto(manifiesto.hash)}</code>
            </dd>
          </div>
        )}
        {modelo.evaluado_en && (
          <div>
            <dt>Evaluado</dt>
            <dd>
              {fechaLocal(modelo.evaluado_en)}
              {duracionS !== null && <span className="suave"> · {numero(duracionS, 1)} s</span>}
            </dd>
          </div>
        )}
        {modelo.evaluador_id && (
          <div>
            <dt>Evaluador</dt>
            <dd>
              <code>{modelo.evaluador_id}</code>
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
