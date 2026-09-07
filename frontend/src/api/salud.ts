import { get } from "./cliente";
import type { Salud } from "./tipos";

export function consultar(): Promise<Salud> {
  return get<Salud>("/health");
}
