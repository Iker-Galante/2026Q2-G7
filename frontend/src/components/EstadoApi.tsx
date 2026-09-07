import type { Salud } from "../api/tipos";

interface Props {
  salud: Salud | null;
  consultado: boolean;
}

/** Indicador de salud de la API para el pie de página. */
export default function EstadoApi({ salud, consultado }: Props) {
  if (!consultado) {
    return <span className="estado-api">API: consultando…</span>;
  }
  if (salud === null) {
    return (
      <span className="estado-api caido">
        <span className="punto" /> API: sin respuesta
      </span>
    );
  }
  return (
    <span className="estado-api ok">
      <span className="punto" /> API: ok · instancia <code>{salud.instancia}</code>
    </span>
  );
}
