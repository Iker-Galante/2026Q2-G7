/**
 * Lo que el sitio sabe de la infraestructura. En AWS lo escribe Terraform en
 * /config.json, al lado del index.html del bucket web (terraform/config.tf):
 * así el mismo build sirve para cualquier cuenta y no hay que recompilar
 * cuando cambia la dirección de API Gateway.
 *
 * Sin ese archivo (docker compose, `npm run dev`) la API es relativa, del mismo
 * origen, y no hay login.
 */

export interface ConfigCognito {
  /** https://<prefijo>.auth.<región>.amazoncognito.com */
  dominio: string;
  clienteId: string;
  /** GET /callback de API Gateway: el redirect_uri que canjea la Lambda. */
  callback: string;
  /** GET /logout de API Gateway: rebota al sitio. */
  logout: string;
}

export interface Configuracion {
  /** Origen de la API, sin barra final. "" = el mismo del sitio. */
  api: string;
  /** null = sin login: todos los pedidos van sin token. */
  cognito: ConfigCognito | null;
}

let actual: Configuracion = { api: "", cognito: null };

function esCognito(valor: unknown): valor is ConfigCognito {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return ["dominio", "clienteId", "callback", "logout"].every((k) => typeof v[k] === "string");
}

/** Se llama una vez, antes de pintar. Si falla, queda la configuración local. */
export async function cargarConfiguracion(): Promise<void> {
  try {
    const respuesta = await fetch("/config.json", { cache: "no-store" });
    // En local el backend (o Vite) contesta index.html para lo que no existe: no es JSON.
    if (!respuesta.ok || !(respuesta.headers.get("content-type") ?? "").includes("json")) return;
    const cuerpo = (await respuesta.json()) as Record<string, unknown>;
    actual = {
      api: typeof cuerpo.api === "string" ? cuerpo.api.replace(/\/+$/, "") : "",
      cognito: esCognito(cuerpo.cognito) ? cuerpo.cognito : null,
    };
  } catch {
    // Sin red o JSON roto: seguimos como en local.
  }
}

export function configuracion(): Configuracion {
  return actual;
}
