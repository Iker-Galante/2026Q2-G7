import { useCallback, useEffect, useRef, useState } from "react";
import { mensajeDeError } from "../api/cliente";
import { crearSubida, obtener, publicar as publicarEnApi } from "../api/modelos";
import { subirArchivoAS3 } from "../api/s3";
import type { ContratoModelo, Modelo } from "../api/tipos";

const INTERVALO_MS = 3000;

export interface OpcionesPublicacion {
  /** Se llama con el modelo recién publicado (202), antes de empezar a seguirlo. */
  alPublicar: (modelo: Modelo) => void;
  /** Se llama en cada vuelta del polling con el modelo actualizado. */
  alActualizar: (modelo: Modelo) => void;
}

/** "subiendo" solo existe cuando el modelo llega desde la interfaz. */
export type EtapaPublicacion = "idle" | "subiendo" | "publicando";

export interface EstadoPublicacion {
  publicando: boolean;
  etapa: EtapaPublicacion;
  /** Fracción subida del ONNX, 0..1. */
  progreso: number;
  /** Id del modelo cuya evaluación se está siguiendo, o null. */
  idSeguido: string | null;
  error: string | null;
  publicar: (nombre: string, version: string) => Promise<void>;
  /** Sube el ONNX al bucket y publica el modelo con su contrato. */
  subirYPublicar: (archivo: File, contrato: ContratoModelo) => Promise<void>;
  /** Sigue la evaluación de un modelo ya publicado (pendiente / en_curso). */
  seguir: (id: string) => void;
  limpiarError: () => void;
}

/**
 * Publica un modelo —ya sea uno que estaba en el bucket o uno que se acaba de
 * subir desde la interfaz— y sigue su evaluación consultando GET /modelos/{id}
 * cada 3 s hasta que el estado sea "ok" o "error".
 */
export function usePublicacion(opciones: OpcionesPublicacion): EstadoPublicacion {
  const [publicando, setPublicando] = useState(false);
  const [etapa, setEtapa] = useState<EtapaPublicacion>("idle");
  const [progreso, setProgreso] = useState(0);
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

  // Lo que sigue al 202: avisar al padre y, si quedó en cola, seguirlo.
  const alDarDeAlta = useCallback((modelo: Modelo) => {
    callbacks.current.alPublicar(modelo);
    const terminado = modelo.estado_evaluacion === "ok" || modelo.estado_evaluacion === "error";
    setIdSeguido(terminado ? null : modelo.id);
  }, []);

  const publicar = useCallback(
    async (nombre: string, version: string) => {
      setPublicando(true);
      setEtapa("publicando");
      setError(null);
      try {
        const modelo = await publicarEnApi({ nombre, version });
        if (!montado.current) return;
        alDarDeAlta(modelo);
      } catch (e) {
        if (!montado.current) return;
        setError(mensajeDeError(e));
      } finally {
        if (montado.current) {
          setPublicando(false);
          setEtapa("idle");
        }
      }
    },
    [alDarDeAlta],
  );

  /**
   * El camino completo desde la interfaz:
   *  1. POST /modelos/subidas reserva el prefijo y firma la subida,
   *  2. el ONNX va del navegador al bucket (con progreso),
   *  3. POST /modelos/publicar manda el contrato: la API lo valida, confirma
   *     que el archivo llegó, escribe el modelo.json y da de alta el modelo.
   */
  const subirYPublicar = useCallback(
    async (archivo: File, contrato: ContratoModelo) => {
      const nombre = typeof contrato.nombre === "string" ? contrato.nombre : "";
      const version = typeof contrato.version === "string" ? contrato.version : "";
      if (nombre === "" || version === "") {
        setError("El contrato tiene que declarar «nombre» y «version».");
        return;
      }
      setPublicando(true);
      setEtapa("subiendo");
      setProgreso(0);
      setError(null);
      try {
        const destino = await crearSubida({ nombre, version, tamano_bytes: archivo.size });
        if (!montado.current) return;
        await subirArchivoAS3(destino.subida, archivo, (fraccion) => {
          if (montado.current) setProgreso(fraccion);
        });
        if (!montado.current) return;

        setEtapa("publicando");
        const modelo = await publicarEnApi({ nombre, version, contrato });
        if (!montado.current) return;
        alDarDeAlta(modelo);
      } catch (e) {
        if (!montado.current) return;
        setError(mensajeDeError(e));
      } finally {
        if (montado.current) {
          setPublicando(false);
          setEtapa("idle");
        }
      }
    },
    [alDarDeAlta],
  );

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

  return { publicando, etapa, progreso, idSeguido, error, publicar, subirYPublicar, seguir, limpiarError };
}
