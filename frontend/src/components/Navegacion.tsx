import type { Salud } from "../api/tipos";
import { Enlace } from "../enrutador";
import type { Tema } from "../hooks/useTema";
import EstadoApi from "./EstadoApi";
import Marca from "./Marca";

interface Props {
  salud: Salud | null;
  consultado: boolean;
  tema: Tema;
  onAlternarTema: () => void;
}

function IconoTema({ tema }: { tema: Tema }) {
  if (tema === "oscuro") {
    // Sol: al estar en oscuro, el botón lleva a claro.
    return (
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2.6v2.4M12 19v2.4M2.6 12H5M19 12h2.4M5.4 5.4l1.7 1.7M16.9 16.9l1.7 1.7M18.6 5.4l-1.7 1.7M7.1 16.9l-1.7 1.7" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a6.8 6.8 0 0 0 11.1 11.1Z" strokeLinejoin="round" />
    </svg>
  );
}

/** Barra superior: marca, las tres vistas, salud de la API y tema. */
export default function Navegacion({ salud, consultado, tema, onAlternarTema }: Props) {
  return (
    <header className="barra">
      <div className="barra-interior">
        <Enlace a="/" className="logo">
          <Marca />
          <span className="logo-texto">Ateneo</span>
        </Enlace>

        <nav className="menu" aria-label="Secciones">
          <Enlace a="/">Inicio</Enlace>
          <Enlace a="/publicar">Publicar modelo</Enlace>
          <Enlace a="/consulta">Consultar estudio</Enlace>
        </nav>

        <div className="barra-fin">
          <EstadoApi salud={salud} consultado={consultado} variante="compacto" />
          <button
            type="button"
            className="boton-icono"
            onClick={onAlternarTema}
            aria-label={tema === "oscuro" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
            title={tema === "oscuro" ? "Tema claro" : "Tema oscuro"}
          >
            <IconoTema tema={tema} />
          </button>
        </div>
      </div>
    </header>
  );
}
