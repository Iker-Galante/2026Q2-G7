import { get } from "./cliente";
import type { Trabajo } from "./tipos";

export function obtener(id: string): Promise<Trabajo> {
  return get<Trabajo>(`/trabajos/${encodeURIComponent(id)}`);
}
