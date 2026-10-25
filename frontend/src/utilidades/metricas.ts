// Lectura de las métricas libres que deja el evaluador y del catálogo en conjunto.

import type { Modelo } from "../api/tipos";

export function leerNumero(metricas: Record<string, unknown> | null, clave: string): number | null {
  const valor = metricas?.[clave];
  return typeof valor === "number" && Number.isFinite(valor) ? valor : null;
}

/** Cuántos casos tuvo la evaluación: lo que midió el evaluador o, si no, el manifiesto. */
export function casosDe(m: Modelo): number | null {
  return leerNumero(m.metricas, "n_casos") ?? m.manifiesto?.casos ?? null;
}

/** El mejor modelo evaluado de cada tipo de estudio, solo donde hay con qué comparar. */
export function lideres(modelos: Modelo[]): Set<string> {
  const porTipo = new Map<string, Modelo[]>();
  for (const m of modelos) {
    if (m.estado_evaluacion !== "ok" || m.accuracy === null) continue;
    porTipo.set(m.tipo_estudio, [...(porTipo.get(m.tipo_estudio) ?? []), m]);
  }
  const ids = new Set<string>();
  for (const lista of porTipo.values()) {
    if (lista.length < 2) continue;
    ids.add(lista.reduce((a, b) => ((b.accuracy ?? 0) > (a.accuracy ?? 0) ? b : a)).id);
  }
  return ids;
}

/** Un tono estable por tipo de estudio, para que las tarjetas de un mismo tipo se reconozcan. */
export function tonoDe(tipo: string): number {
  let h = 0;
  for (const c of tipo) h = (h * 31 + c.charCodeAt(0)) % 360;
  // Entre los verdes azulados y los azules: la paleta de la marca.
  return 160 + (h % 70);
}

/** Los tipos del catálogo inicial tienen nombre propio; el resto, al menos "torax rx". */
const TIPOS: Record<string, string> = {
  "torax-rx": "Tórax · RX",
  "cerebro-rm": "Cerebro · RM",
};

export function nombreTipo(tipo: string): string {
  return TIPOS[tipo] ?? tipo.replace(/[-_]+/g, " ");
}
