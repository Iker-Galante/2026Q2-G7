import { useCallback, useEffect, useRef, useState } from "react";
import { mensajeDeError } from "../api/cliente";
import { listarDisponibles, listarPublicados } from "../api/modelos";
import type { Modelo, ModeloDisponible } from "../api/tipos";

export interface EstadoModelos {
  publicados: Modelo[];
  disponibles: ModeloDisponible[];
  cargando: boolean;
  error: string | null;
  /** Vuelve a pedir las dos listas. */
  refrescar: () => Promise<void>;
  /** Reemplaza (o agrega al frente) un modelo en la lista de publicados. */
  actualizarModelo: (modelo: Modelo) => void;
}

/** Carga los modelos publicados y los disponibles en el bucket. */
export function useModelos(): EstadoModelos {
  const [publicados, setPublicados] = useState<Modelo[]>([]);
  const [disponibles, setDisponibles] = useState<ModeloDisponible[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const montado = useRef(true);

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  const refrescar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [p, d] = await Promise.all([listarPublicados(), listarDisponibles()]);
      if (!montado.current) return;
      setPublicados(p);
      setDisponibles(d);
    } catch (e) {
      if (!montado.current) return;
      setError(mensajeDeError(e));
    } finally {
      if (montado.current) setCargando(false);
    }
  }, []);

  useEffect(() => {
    void refrescar();
  }, [refrescar]);

  const actualizarModelo = useCallback((modelo: Modelo) => {
    setPublicados((previos) =>
      previos.some((m) => m.id === modelo.id)
        ? previos.map((m) => (m.id === modelo.id ? modelo : m))
        : [modelo, ...previos],
    );
  }, []);

  return { publicados, disponibles, cargando, error, refrescar, actualizarModelo };
}
