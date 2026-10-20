import type { CSSProperties } from "react";
import type { Modelo } from "../api/tipos";
import { Enlace, rutaDeModelo } from "../enrutador";
import { porcentaje } from "../utilidades/formato";
import { casosDe, nombreTipo, tonoDe } from "../utilidades/metricas";
import EstadoModelo from "./EstadoModelo";
import Marca from "./Marca";
import { Flecha } from "./Navegacion";

interface Props {
  modelo: Modelo;
  /** Es el de mejor accuracy de su tipo de estudio. */
  mejor?: boolean;
}

/** Un modelo del catálogo como tarjeta; toda la tarjeta lleva a su ficha. */
export default function TarjetaModelo({ modelo: m, mejor = false }: Props) {
  const casos = casosDe(m);
  const evaluado = m.estado_evaluacion === "ok" && m.accuracy !== null;
  const estilo = { "--tono": tonoDe(m.tipo_estudio) } as CSSProperties;

  return (
    <Enlace a={rutaDeModelo(m.id)} className="tarjeta-modelo">
      <div className="tm-visual" style={estilo}>
        <span className="tm-tipo">{nombreTipo(m.tipo_estudio)}</span>
        <EstadoModelo estado={m.estado_evaluacion} />
        <span className="tm-marca" aria-hidden="true">
          <Marca tamano={140} />
        </span>
        {evaluado && <span className="tm-accuracy">{porcentaje(m.accuracy ?? 0)}</span>}
      </div>

      <div className="tm-cuerpo">
        <div className="tm-titulo">
          <h3>{m.nombre}</h3>
          <span className="version">v{m.version}</span>
          {mejor && <span className="pastilla destacada">Mejor del tipo</span>}
        </div>
        <p className="tm-etiquetas">{m.etiquetas.join(" · ") || m.tarea}</p>
        <div className="tm-pie">
          <span>
            {evaluado
              ? `Listo para usar · ${casos ?? "—"} casos evaluados`
              : m.estado_evaluacion === "error"
                ? "La evaluación no terminó"
                : "Esperando la evaluación"}
          </span>
          <span className="tm-ir" aria-hidden="true">
            <Flecha />
          </span>
        </div>
      </div>
    </Enlace>
  );
}
