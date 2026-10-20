import type { EstadoDemo as Estado } from "../hooks/useModelos";

export default function EstadoDemo({ demo }: { demo: Estado | null }) {
  if (!demo?.activo || demo.estado === "ok") return null;
  return (
    <div className={demo.estado === "error" ? "caja-error" : "nota-suave"} role="status">
      {demo.estado === "error"
        ? "No se pudo preparar el modelo de demostración. El administrador puede revisar la inicialización y reintentar."
        : "Estamos preparando y evaluando el modelo de demostración. Aparecerá automáticamente cuando esté listo; no necesitás subir uno."}
    </div>
  );
}
