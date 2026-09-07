import { useCallback, useEffect, useRef, useState } from "react";
import { mensajeDeError } from "../api/cliente";
import { crear as crearEstudio, subirArchivoAS3 } from "../api/estudios";
import { encolar } from "../api/inferencias";
import { obtener as obtenerTrabajo } from "../api/trabajos";
import type { Modelo, Trabajo } from "../api/tipos";

const INTERVALO_MS = 1500;
const TIEMPO_MAXIMO_MS = 5 * 60 * 1000;

export type EtapaInferencia =
  | "idle"
  | "subiendo"
  | "encolando"
  | "esperando"
  | "ok"
  | "error";

export interface EstadoInferencia {
  etapa: EtapaInferencia;
  trabajo: Trabajo | null;
  error: string | null;
  /** true mientras hay una corrida en marcha (subiendo, encolando o esperando). */
  enCurso: boolean;
  ejecutar: (archivo: File, modelo: Modelo) => Promise<void>;
  reiniciar: () => void;
}

/**
 * Flujo completo de una inferencia:
 *  1. POST /estudios con los metadatos del archivo,
 *  2. subida a S3 con el presigned POST,
 *  3. POST /inferencias,
 *  4. polling de GET /trabajos/{id} cada 1,5 s hasta ok / error (máx. 5 min).
 */
export function useInferencia(): EstadoInferencia {
  const [etapa, setEtapa] = useState<EtapaInferencia>("idle");
  const [trabajo, setTrabajo] = useState<Trabajo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idTrabajo, setIdTrabajo] = useState<string | null>(null);

  const montado = useRef(true);
  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
    };
  }, []);

  const ejecutar = useCallback(async (archivo: File, modelo: Modelo) => {
    setError(null);
    setTrabajo(null);
    setIdTrabajo(null);
    try {
      setEtapa("subiendo");
      const estudio = await crearEstudio({
        tipo_estudio: modelo.tipo_estudio,
        nombre_archivo: archivo.name,
        content_type: archivo.type,
        tamano_bytes: archivo.size,
      });
      await subirArchivoAS3(estudio.subida, archivo);
      if (!montado.current) return;

      setEtapa("encolando");
      const encolado = await encolar({
        estudio_id: estudio.estudio_id,
        modelo_id: modelo.id,
      });
      if (!montado.current) return;

      setTrabajo(encolado);
      setEtapa("esperando");
      setIdTrabajo(encolado.id);
    } catch (e) {
      if (!montado.current) return;
      setError(mensajeDeError(e));
      setEtapa("error");
    }
  }, []);

  const reiniciar = useCallback(() => {
    setIdTrabajo(null);
    setTrabajo(null);
    setError(null);
    setEtapa("idle");
  }, []);

  // Polling del trabajo; se cancela al terminar, al reiniciar o al desmontar.
  useEffect(() => {
    if (idTrabajo === null) return;
    const id = idTrabajo;
    const inicio = Date.now();
    let activo = true;
    let temporizador: ReturnType<typeof setInterval> | undefined;

    const terminar = () => {
      activo = false;
      if (temporizador !== undefined) clearInterval(temporizador);
    };

    const consultar = async () => {
      if (!activo) return;
      if (Date.now() - inicio > TIEMPO_MAXIMO_MS) {
        terminar();
        setError("El trabajo no terminó en 5 minutos. Probá de nuevo más tarde.");
        setEtapa("error");
        return;
      }
      try {
        const actual = await obtenerTrabajo(id);
        if (!activo) return;
        setTrabajo(actual);
        if (actual.estado === "ok") {
          terminar();
          setEtapa("ok");
        } else if (actual.estado === "error") {
          terminar();
          setError(actual.error ?? "La inferencia falló sin detalle.");
          setEtapa("error");
        }
      } catch (e) {
        if (!activo) return;
        terminar();
        setError(mensajeDeError(e));
        setEtapa("error");
      }
    };

    temporizador = setInterval(() => void consultar(), INTERVALO_MS);
    void consultar();

    return terminar;
  }, [idTrabajo]);

  const enCurso = etapa === "subiendo" || etapa === "encolando" || etapa === "esperando";

  return { etapa, trabajo, error, enCurso, ejecutar, reiniciar };
}
