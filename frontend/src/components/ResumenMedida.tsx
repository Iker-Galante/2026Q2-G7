import type { Modelo } from "../api/tipos";
import { porcentaje } from "../utilidades/formato";

interface Props {
  modelo: Modelo;
}

function leerNumero(metricas: Record<string, unknown> | null, clave: string): number | null {
  const valor = metricas?.[clave];
  return typeof valor === "number" && Number.isFinite(valor) ? valor : null;
}

/** Contra qué se midió el modelo elegido: el contexto de la predicción. */
export default function ResumenMedida({ modelo }: Props) {
  if (modelo.estado_evaluacion !== "ok") {
    return (
      <p className="ayuda">
        Este modelo todavía no tiene una medida propia: la predicción llega sin accuracy con la que
        ponerla en contexto.
      </p>
    );
  }

  const sensibilidad = leerNumero(modelo.metricas, "sensibilidad");
  const especificidad = leerNumero(modelo.metricas, "especificidad");
  const casos = leerNumero(modelo.metricas, "n_casos") ?? modelo.manifiesto?.casos ?? null;

  return (
    <dl className="tira tira-chica">
      {modelo.accuracy !== null && (
        <div>
          <dt>Accuracy</dt>
          <dd>{porcentaje(modelo.accuracy)}</dd>
        </div>
      )}
      {sensibilidad !== null && (
        <div>
          <dt>Sensibilidad</dt>
          <dd>{porcentaje(sensibilidad)}</dd>
        </div>
      )}
      {especificidad !== null && (
        <div>
          <dt>Especificidad</dt>
          <dd>{porcentaje(especificidad)}</dd>
        </div>
      )}
      {casos !== null && (
        <div>
          <dt>Casos</dt>
          <dd>{casos}</dd>
        </div>
      )}
      {modelo.conjunto && (
        <div>
          <dt>Conjunto</dt>
          <dd>
            {modelo.conjunto}
            {modelo.conjunto_version ? ` ${modelo.conjunto_version}` : ""}
          </dd>
        </div>
      )}
    </dl>
  );
}
