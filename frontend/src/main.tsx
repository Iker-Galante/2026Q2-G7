import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { cargarConfiguracion } from "./api/configuracion";
import { recibirDelCallback } from "./api/sesion";
import "./estilos.css";

const raiz = document.getElementById("root");
if (raiz === null) throw new Error("No existe el elemento #root en index.html");
const contenedor = raiz;

// Antes de pintar: dónde está la API y si venimos del login con los tokens en la URL.
async function arrancar(): Promise<void> {
  await cargarConfiguracion();
  const errorIngreso = recibirDelCallback();
  createRoot(contenedor).render(
    <StrictMode>
      <App errorIngreso={errorIngreso} />
    </StrictMode>,
  );
}

void arrancar();
