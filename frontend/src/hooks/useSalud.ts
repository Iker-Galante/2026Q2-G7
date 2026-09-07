import { useEffect, useState } from "react";
import { consultar } from "../api/salud";
import type { Salud } from "../api/tipos";

const INTERVALO_MS = 10_000;

/**
 * Consulta GET /health al montar y cada 10 s.
 * `salud` es null hasta la primera respuesta o cuando la API no contesta.
 */
export function useSalud(): { salud: Salud | null; consultado: boolean } {
  const [salud, setSalud] = useState<Salud | null>(null);
  const [consultado, setConsultado] = useState(false);

  useEffect(() => {
    let activo = true;

    const pedir = async () => {
      try {
        const respuesta = await consultar();
        if (activo) setSalud(respuesta.ok ? respuesta : null);
      } catch {
        if (activo) setSalud(null);
      } finally {
        if (activo) setConsultado(true);
      }
    };

    void pedir();
    const temporizador = setInterval(() => void pedir(), INTERVALO_MS);
    return () => {
      activo = false;
      clearInterval(temporizador);
    };
  }, []);

  return { salud, consultado };
}
