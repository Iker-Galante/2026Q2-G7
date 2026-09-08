// Ruteo del lado del cliente, tres rutas y sin librerías.
//
// El backend devuelve index.html para cualquier ruta fuera de /api (sitio.py),
// así que History API alcanza: no hace falta hash ni configuración de servidor.
// Si algún día entra react-router, lo único que cambia es este archivo y el
// componente Enlace; las páginas y los hooks no lo notan.

import { useSyncExternalStore } from "react";
import type { MouseEvent, ReactNode } from "react";

const RUTAS = ["/", "/publicar", "/consulta"] as const;

export type Ruta = (typeof RUTAS)[number];

/** Cualquier ruta desconocida cae en el inicio. */
function normalizar(pathname: string): Ruta {
  const limpia = pathname.replace(/\/+$/, "") || "/";
  return (RUTAS as readonly string[]).includes(limpia) ? (limpia as Ruta) : "/";
}

const oyentes = new Set<() => void>();

function avisar(): void {
  for (const oyente of oyentes) oyente();
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  window.addEventListener("popstate", avisar);
  return () => {
    oyentes.delete(oyente);
    if (oyentes.size === 0) window.removeEventListener("popstate", avisar);
  };
}

const leer = (): string => window.location.pathname;

/** Ruta actual; se re-renderiza al navegar o al usar atrás/adelante. */
export function useRuta(): Ruta {
  return normalizar(useSyncExternalStore(suscribir, leer, () => "/"));
}

export function navegar(ruta: Ruta): void {
  if (normalizar(window.location.pathname) === ruta) return;
  window.history.pushState({}, "", ruta);
  window.scrollTo({ top: 0 });
  avisar();
}

interface PropsEnlace {
  a: Ruta;
  className?: string;
  children: ReactNode;
}

/** <a> real (se puede abrir en otra pestaña) que navega sin recargar. */
export function Enlace({ a, className, children }: PropsEnlace) {
  const actual = useRuta();

  const alHacerClic = (e: MouseEvent<HTMLAnchorElement>) => {
    // Ctrl/Cmd/Shift o botón del medio: que lo maneje el navegador.
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
      return;
    }
    e.preventDefault();
    navegar(a);
  };

  return (
    <a href={a} className={className} aria-current={actual === a ? "page" : undefined} onClick={alHacerClic}>
      {children}
    </a>
  );
}
