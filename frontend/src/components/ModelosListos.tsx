import type { Modelo } from "../api/tipos";
import { Enlace } from "../enrutador";
import { Flecha } from "./Navegacion";

export default function ModelosListos({ modelos, conEnlace = false }: { modelos: Modelo[]; conEnlace?: boolean }) {
  const cantidad = modelos.filter((m) => m.estado_evaluacion === "ok" && m.accuracy !== null).length;
  if (cantidad === 0) return null;

  return (
    <div className="modelos-listos" role="status">
      <div>
        <span className="pastilla ok">{cantidad} {cantidad === 1 ? "modelo listo" : "modelos listos"}</span>
        <p><strong>No necesitás publicar un modelo para empezar.</strong></p>
        <p>Elegí uno del catálogo, abrí su ficha y subí una imagen para analizar. Publicar uno propio es opcional.</p>
      </div>
      {conEnlace && (
        <Enlace a="/modelos" className="pildora pildora-oscura">
          Usar los modelos disponibles <Flecha />
        </Enlace>
      )}
    </div>
  );
}
