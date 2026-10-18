import { useEffect, useState } from "react";
import { ErrorApi, mensajeDeError } from "../api/cliente";
import { obtener } from "../api/modelos";
import type { Modelo } from "../api/tipos";

const INTERVALO_MS = 4000;

export interface EstadoModelo {
  modelo: Modelo | null;
  cargando: boolean;
  /** El id no existe en el catálogo. */
  noExiste: boolean;
  error: string | null;
}

/**
 * La ficha de un modelo. Mientras su evaluación está en cola o corriendo, la vuelve a
 * pedir cada 4 s, así la página pasa sola de «evaluando» a las métricas.
 */
export function useModelo(id: string): EstadoModelo {
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [noExiste, setNoExiste] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const estado = modelo?.estado_evaluacion;
  const sigueEvaluando = estado === "pendiente" || estado === "en_curso";

  useEffect(() => {
    let vivo = true;
    let temporizador: number | undefined;

    const pedir = async () => {
      try {
        const m = await obtener(id);
        if (!vivo) return;
        setModelo(m);
        setError(null);
      } catch (e) {
        if (!vivo) return;
        if (e instanceof ErrorApi && (e.status === 404 || e.status === 422)) setNoExiste(true);
        else setError(mensajeDeError(e));
      } finally {
        if (vivo) setCargando(false);
      }
    };

    if (modelo === null || sigueEvaluando) {
      if (modelo === null) void pedir();
      else temporizador = window.setTimeout(() => void pedir(), INTERVALO_MS);
    }

    return () => {
      vivo = false;
      window.clearTimeout(temporizador);
    };
    // `modelo` cambia en cada vuelta y eso es lo que programa la siguiente.
  }, [id, modelo, sigueEvaluando]);

  return { modelo, cargando, noExiste, error };
}
