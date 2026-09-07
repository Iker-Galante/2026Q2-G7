import { useCallback, useEffect, useRef, useState } from "react";
import { mensajeDeError } from "../api/cliente";
import { obtener, publicar as publicarEnApi } from "../api/modelos";
import type { Modelo } from "../api/tipos";

const INTERVALO_MS = 3000;

export interface OpcionesPublicacion {
  /** Se llama con el modelo recién publicado (202), antes de empezar a seguirlo. */
  alPublicar: (modelo: Modelo) => void;
  /** Se llama en cada vuelta del polling con el modelo actualizado. */
  alActualizar: (modelo: Modelo) => void;
}

export interface EstadoPublicacion {
  publicando: boolean;
  /** Id del modelo cuya evaluación se está siguiendo, o null. */
  idSeguido: string | null;
  error: string | null;
  publicar: (nombre: string, version: string) => Promise<void>;
  /** Sigue la evaluación de un modelo ya publicado (pendiente / en_curso). */
  seguir: (id: string) => void;
  limpiarError: () => void;
}

/**
 * Publica un modelo y sigue su evaluación consultando GET /modelos/{id}
 * cada 3 s hasta que el estado sea "ok" o "error".
 */
export function usePublicacion(opciones: OpcionesPublicacion): EstadoPublicacion {
  const [publicando, setPublicando] = useState(false);
  const [idSeguido, setIdSeguido] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Guardamos los callbacks en un ref para que el polling no se reinicie
  // cada vez que el padre re-renderiza con funciones nuevas.
  const callbacks = useRef(opciones);
  useEffect(() => {
    callbacks.current = opciones;
  }, [opciones]);

  const montado = useRef(true);
  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  const publicar = useCallback(async (nombre: string, version: string) => {
    setPublicando(true);
    setError(null);
    try {
      const modelo = await publicarEnApi({ nombre, version });
      if (!montado.current) return;
      callbacks.current.alPublicar(modelo);
      const terminado =
        modelo.estado_evaluacion === "ok" || modelo.estado_evaluacion === "error";
      setIdSeguido(terminado ? null : modelo.id);
    } catch (e) {
      if (!montado.current) return;
      setError(mensajeDeError(e));
    } finally {
      if (montado.current) setPublicando(false);
    }
  }, []);

  const seguir = useCallback((id: string) => {
    setIdSeguido((actual) => (actual === id ? actual : id));
  }, []);

  const limpiarError = useCallback(() => setError(null), []);

  // Polling: vive mientras haya un id seguido; se cancela al terminar o al desmontar.
  useEffect(() => {
    if (idSeguido === null) return;
    const id = idSeguido;
    let activo = true;

    const consultar = async () => {
      try {
        const modelo = await obtener(id);
        if (!activo) return;
        callbacks.current.alActualizar(modelo);
        if (modelo.estado_evaluacion === "ok" || modelo.estado_evaluacion === "error") {
          setIdSeguido((actual) => (actual === id ? null : actual));
        }
      } catch (e) {
        if (!activo) return;
        setError(mensajeDeError(e));
        setIdSeguido((actual) => (actual === id ? null : actual));
      }
    };

    const temporizador = setInterval(() => void consultar(), INTERVALO_MS);
    return () => {
      activo = false;
      clearInterval(temporizador);
    };
  }, [idSeguido]);

  return { publicando, idSeguido, error, publicar, seguir, limpiarError };
}
