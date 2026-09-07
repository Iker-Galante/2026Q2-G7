import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ModeloDisponible } from "../api/tipos";
import { etiquetaModelo } from "../utilidades/formato";

interface Props {
  disponibles: ModeloDisponible[];
  publicando: boolean;
  error: string | null;
  onPublicar: (nombre: string, version: string) => void;
  onLimpiarError: () => void;
}

function clave(m: ModeloDisponible): string {
  return `${m.nombre}@${m.version}`;
}

/** Elegir un modelo del bucket y darlo de alta. */
export default function PanelPublicar({
  disponibles,
  publicando,
  error,
  onPublicar,
  onLimpiarError,
}: Props) {
  const [claveElegida, setClaveElegida] = useState<string>("");

  // Preseleccionamos el primer modelo sin publicar (o el primero a secas).
  useEffect(() => {
    if (disponibles.length === 0) {
      setClaveElegida("");
      return;
    }
    setClaveElegida((actual) => {
      if (disponibles.some((m) => clave(m) === actual)) return actual;
      const sinPublicar = disponibles.find((m) => !m.publicado) ?? disponibles[0];
      return clave(sinPublicar);
    });
  }, [disponibles]);

  const elegido = disponibles.find((m) => clave(m) === claveElegida) ?? null;

  const enviar = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (elegido === null || publicando) return;
    onPublicar(elegido.nombre, elegido.version);
  };

  return (
    <form className="tarjeta" onSubmit={enviar}>
      <h3>Publicar un modelo</h3>

      {disponibles.length === 0 ? (
        <p className="vacio">No hay modelos en el bucket.</p>
      ) : (
        <label className="campo">
          <span className="campo-etiqueta">Modelo en el bucket</span>
          <select
            value={claveElegida}
            disabled={publicando}
            onChange={(e) => {
              setClaveElegida(e.target.value);
              onLimpiarError();
            }}
          >
            {disponibles.map((m) => (
              <option key={clave(m)} value={clave(m)}>
                {etiquetaModelo(m)}
                {m.publicado ? " (publicado)" : ""}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="fila-accion">
        <button type="submit" disabled={elegido === null || publicando}>
          {publicando ? "Publicando…" : "Publicar modelo"}
        </button>
        {publicando && <span className="spinner" aria-hidden="true" />}
      </div>
      <p className="ayuda">
        Simula la subida de un modelo: lo da de alta y lo evalúa contra el conjunto reservado en
        eval-1.
      </p>

      {error && (
        <div className="caja-error" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}
