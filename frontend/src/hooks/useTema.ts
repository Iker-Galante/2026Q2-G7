import { useCallback, useEffect, useState } from "react";

export type Tema = "claro" | "oscuro";

const CLAVE = "ateneo:tema";

/** Lo que dejó el script de index.html, o la preferencia del sistema. */
function temaInicial(): Tema {
  const atributo = document.documentElement.dataset.theme;
  if (atributo === "dark") return "oscuro";
  if (atributo === "light") return "claro";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "oscuro" : "claro";
}

/**
 * Tema claro / oscuro. Sin elección explícita manda el sistema (los tokens de
 * CSS ya responden a prefers-color-scheme); al elegir, queda en localStorage y
 * se escribe `data-theme` en <html>, que gana sobre el media query.
 */
export function useTema(): { tema: Tema; alternar: () => void } {
  const [tema, setTema] = useState<Tema>(temaInicial);

  useEffect(() => {
    document.documentElement.dataset.theme = tema === "oscuro" ? "dark" : "light";
  }, [tema]);

  const alternar = useCallback(() => {
    setTema((actual) => {
      const nuevo: Tema = actual === "oscuro" ? "claro" : "oscuro";
      try {
        window.localStorage.setItem(CLAVE, nuevo);
      } catch {
        // Modo privado o almacenamiento bloqueado: el tema vale para esta visita.
      }
      return nuevo;
    });
  }, []);

  return { tema, alternar };
}
