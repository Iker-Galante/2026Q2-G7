import type { Salud } from "../api/tipos";

interface Props {
  salud: Salud | null;
  consultado: boolean;
  /** "compacto" para la barra superior; "detallado" agrega la instancia. */
  variante?: "compacto" | "detallado";
}

/** Indicador de salud de la API: un punto y, si se pide, qué instancia contestó. */
export default function EstadoApi({ salud, consultado, variante = "detallado" }: Props) {
  if (!consultado) {
    return (
      <span className="estado-api" title="Consultando /api/health">
        <span className="punto" /> API…
      </span>
    );
  }

  if (salud === null) {
    return (
      <span className="estado-api caido" title="La API no respondió a /api/health">
        <span className="punto" /> API sin respuesta
      </span>
    );
  }

  return (
    <span className="estado-api ok" title={`Atendió la instancia ${salud.instancia}`}>
      <span className="punto" /> API ok
      {variante === "detallado" && (
        <>
          {" · instancia "}
          <code>{salud.instancia}</code>
        </>
      )}
    </span>
  );
}
