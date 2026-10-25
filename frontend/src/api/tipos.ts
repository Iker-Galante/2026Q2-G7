// Tipos que devuelve la API de Ateneo. Espejo de specs.md; si cambia el
// backend, cambia acá y el compilador marca el resto.

/** Presigned POST de S3: URL destino + campos que van antes del archivo. */
export interface SubidaPresignada {
  url: string;
  campos: Record<string, string>;
}

export type EstadoEvaluacion = "pendiente" | "en_curso" | "ok" | "error";

export interface MatrizConfusion {
  etiquetas: string[];
  valores: number[][];
}

export interface Manifiesto {
  casos?: number;
  congelado_en?: string;
  hash?: string;
}

export interface Modelo {
  id: string;
  nombre: string;
  nombre_visible: string | null;
  predeterminado: boolean;
  version: string;
  tipo_estudio: string;
  tarea: string;
  etiquetas: string[];
  estado_evaluacion: EstadoEvaluacion;
  /** Exactitud en 0..1; null hasta que termina la evaluación. */
  accuracy: number | null;
  /**
   * Métricas libres del evaluador. Puede traer n_casos, accuracy,
   * precision_macro, sensibilidad_macro, f1_macro (multiclase) o sensibilidad,
   * especificidad, precision, f1, auc (binario), casos_con_error, duracion_s y
   * matriz_confusion.
   */
  metricas: Record<string, unknown> | null;
  conjunto: string | null;
  conjunto_version: string | null;
  manifiesto: Manifiesto | null;
  evaluador_id: string | null;
  evaluado_en: string | null;
  error: string | null;
  creado: string;
  publicado: string;
}

export interface ModeloDisponible {
  nombre: string;
  version: string;
  tipo_estudio: string;
  publicado: boolean;
  modelo_id: string | null;
}

/** El modelo.json tal cual: lo valida la API, así que acá viaja como objeto libre. */
export type ContratoModelo = Record<string, unknown>;

export interface SolicitudPublicar {
  nombre: string;
  version: string;
  /** Presente cuando el modelo se acaba de subir: la API lo escribe en el bucket. */
  contrato?: ContratoModelo;
}

export interface SolicitudSubidaModelo {
  nombre: string;
  version: string;
  tamano_bytes: number;
}

/** Destino en el bucket y el POST prefirmado para mandarle el ONNX. */
export interface SubidaModeloCreada {
  prefix: string;
  subida: SubidaPresignada;
}

export interface SolicitudEstudio {
  tipo_estudio: string;
  nombre_archivo: string;
  content_type: string;
  tamano_bytes: number;
}

export interface EstudioCreado {
  estudio_id: string;
  subida: SubidaPresignada;
}

export interface SolicitudInferencia {
  estudio_id: string;
  modelo_id: string;
}

export type EstadoTrabajo = "pendiente" | "en_curso" | "ok" | "error";

export interface ResultadoTrabajo {
  prediccion: string;
  probabilidades: Record<string, number>;
}

export interface Trabajo {
  id: string;
  estudio_id: string;
  modelo_id: string;
  estado: EstadoTrabajo;
  intentos: number;
  worker_id: string | null;
  duracion_ms: number | null;
  resultado: ResultadoTrabajo | null;
  error: string | null;
  creado: string;
  actualizado: string;
}

export interface Salud {
  ok: boolean;
  instancia: string;
}

/** Cuerpo de error que devuelve el backend en respuestas no 2xx. */
export interface CuerpoError {
  error: string;
  detalle: string;
}
