import type { CSSProperties } from "react";
import type { MatrizConfusion, Modelo } from "../api/tipos";
import { fechaLocal, hashCorto, numero, porcentaje } from "../utilidades/formato";
import { casosDe, leerNumero, nombreTipo } from "../utilidades/metricas";

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

/** Métricas secundarias, en el orden en que se muestran. Solo se listan las presentes. */
const SECUNDARIAS = [
  { clave: "sensibilidad", nombre: "Sensibilidad", esPorcentaje: true },
  { clave: "especificidad", nombre: "Especificidad", esPorcentaje: true },
  { clave: "precision", nombre: "Precisión", esPorcentaje: true },
  { clave: "f1", nombre: "F1", esPorcentaje: true },
  { clave: "auc", nombre: "AUC", esPorcentaje: false },
  { clave: "sensibilidad_macro", nombre: "Sensibilidad macro", esPorcentaje: true },
  { clave: "precision_macro", nombre: "Precisión macro", esPorcentaje: true },
  { clave: "f1_macro", nombre: "F1 macro", esPorcentaje: true },
] as const;

function Matriz({ matriz }: { matriz: MatrizConfusion }) {
  const maximo = Math.max(1, ...matriz.valores.flat());
  return (
    <figure className="matriz">
      <figcaption>Matriz de confusión</figcaption>
      <div className="tabla-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">
                <span className="sr-solo">Real</span>
              </th>
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
                  <td
                    key={j}
                    className={i === j ? "diagonal" : undefined}
                    style={{ "--peso": n / maximo } as CSSProperties}
                  >
                    {n}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="suave">Filas: diagnóstico real · columnas: predicción</p>
    </figure>
  );
}

/** El rendimiento del modelo contra el conjunto reservado, o en qué anda su evaluación. */
export default function RendimientoModelo({ modelo }: { modelo: Modelo }) {
  const { metricas, manifiesto } = modelo;

  if (modelo.estado_evaluacion === "pendiente" || modelo.estado_evaluacion === "en_curso") {
    return (
      <div className="panel-espera">
        <span className="spinner grande" aria-hidden="true" />
        <div>
          <h2>{modelo.estado_evaluacion === "pendiente" ? "En cola de evaluación" : "Evaluando"}</h2>
          <p className="suave">
            Se está midiendo contra el conjunto reservado de {nombreTipo(modelo.tipo_estudio)}. Esta página se
            actualiza sola.
          </p>
        </div>
      </div>
    );
  }

  if (modelo.estado_evaluacion === "error") {
    return (
      <div className="caja-error" role="alert">
        <strong>La evaluación no terminó.</strong>
        <p>{modelo.error ?? "Sin detalle."}</p>
      </div>
    );
  }

  const nCasos = casosDe(modelo);
  const conError = leerNumero(metricas, "casos_con_error");
  const duracionS = leerNumero(metricas, "duracion_s");
  const matriz = metricas?.matriz_confusion;
  const secundarias = SECUNDARIAS.flatMap((d) => {
    const valor = leerNumero(metricas, d.clave);
    return valor === null ? [] : [{ ...d, valor }];
  });

  return (
    <>
      <div className="destacado">
        <span className="destacado-valor">{modelo.accuracy !== null ? porcentaje(modelo.accuracy) : "—"}</span>
        <span className="destacado-nombre">Accuracy sobre {nCasos ?? "—"} casos reservados</span>
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

      {esMatrizConfusion(matriz) && <Matriz matriz={matriz} />}

      <details className="detalle-tecnico">
        <summary>Detalles de la evaluación</summary>
        <dl className="detalles">
          {modelo.conjunto && (
            <div>
              <dt>Conjunto</dt>
              <dd>
                {modelo.conjunto} {modelo.conjunto_version}
              </dd>
            </div>
          )}
          {conError !== null && conError > 0 && (
            <div>
              <dt>Casos ilegibles</dt>
              <dd>{conError}</dd>
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
                {duracionS !== null && ` · ${numero(duracionS, 1)} s`}
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
      </details>
    </>
  );
}
