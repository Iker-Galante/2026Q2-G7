import type { EstadoDemo as Estado } from "../hooks/useModelos";

export default function EstadoDemo({ demo }: { demo: Estado | null }) {
  if (!demo?.activo || demo.estado === "ok") return null;
  return (
    <div className={demo.errores > 0 ? "caja-error" : "nota-suave"} role="status">
      <strong>{demo.listos} de {demo.esperados} modelos iniciales listos.</strong>{" "}
      {demo.pendientes > 0 && "Los demás se están preparando y evaluando; aparecerán automáticamente."}{" "}
      {demo.listos > 0 && "Ya podés usar los modelos listos."}
      {demo.errores > 0 && (
        <p>No se pudieron preparar: {demo.modelos.filter((m) => m.estado === "error").map((m) => m.nombre_visible).join(", ")}. El administrador puede reintentar cada uno sin afectar los demás.</p>
      )}
    </div>
  );
}
