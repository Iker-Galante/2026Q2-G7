import { useCallback, useEffect, useRef, useState } from "react";
import { mensajeDeError } from "../api/cliente";
import { listarDisponibles, listarPublicados } from "../api/modelos";
import type { Modelo, ModeloDisponible } from "../api/tipos";
import { useSesion } from "./useSesion";

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

/**
 * Carga el catálogo y, si hay sesión, los modelos disponibles en el bucket.
 *
 * El catálogo es público, así que la portada lo muestra a quien no ingresó. Lo del bucket pide
 * token: pedirlo sin sesión devolvía 401 y la portada se llenaba de «tu sesión venció».
 */
export function useModelos(): EstadoModelos {
  const { sesion, conLogin } = useSesion();
  const conSesion = !conLogin || sesion !== null;
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
      const [p, d] = await Promise.all([
        listarPublicados(),
        conSesion ? listarDisponibles() : Promise.resolve<ModeloDisponible[]>([]),
      ]);
      if (!montado.current) return;
      setPublicados(p);
      setDisponibles(d);
    } catch (e) {
      if (!montado.current) return;
      setError(mensajeDeError(e));
    } finally {
      if (montado.current) setCargando(false);
    }
  }, [conSesion]);

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
