import { useSyncExternalStore } from "react";
import { configuracion } from "../api/configuracion";
import { sesionActual, suscribirSesion } from "../api/sesion";
import type { Sesion } from "../api/sesion";

/**
 * La sesión de Cognito; se re-renderiza al ingresar, salir o cuando la API
 * rechaza el token. `conLogin` es false en local, donde no hay Cognito.
 */
export function useSesion(): { sesion: Sesion | null; conLogin: boolean } {
  const sesion = useSyncExternalStore(suscribirSesion, sesionActual, () => null);
  return { sesion, conLogin: configuracion().cognito !== null };
}
