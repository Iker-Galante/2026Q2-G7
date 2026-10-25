import type { Modelo } from "../api/tipos";

/** Las opciones incluidas no dependen del ranking ni de cuántos modelos se publiquen luego. */
export function modelosIniciales(publicados: Modelo[], registro?: { nombre: string; version: string }[]): Modelo[] {
  if (!registro) return publicados.filter((m) => m.predeterminado);
  return registro.flatMap((md) => {
    const m = publicados.find((p) => p.nombre === md.nombre && p.version === md.version);
    return m ? [m] : [];
  });
}
