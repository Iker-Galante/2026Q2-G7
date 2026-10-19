import type { EstadoEvaluacion } from "../api/tipos";

const TEXTOS: Record<EstadoEvaluacion, string> = {
  ok: "Evaluado",
  en_curso: "Evaluando",
  pendiente: "En cola",
  error: "Falló",
};

/** Estado de la evaluación de un modelo, como pastilla. */
export default function EstadoModelo({ estado }: { estado: EstadoEvaluacion }) {
  return (
    <span className={`pastilla estado-${estado}`}>
      {estado === "en_curso" ? <span className="spinner" aria-hidden="true" /> : <span className="punto" />}
      {TEXTOS[estado]}
    </span>
  );
}
