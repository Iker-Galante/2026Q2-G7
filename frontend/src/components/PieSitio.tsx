import type { Salud } from "../api/tipos";
import { Enlace } from "../enrutador";
import EstadoApi from "./EstadoApi";
import Marca from "./Marca";

interface Props {
  salud: Salud | null;
  consultado: boolean;
}

export default function PieSitio({ salud, consultado }: Props) {
  return (
    <footer className="pie">
      <div className="pie-interior">
        <div className="pie-marca">
          <Marca tamano={20} />
          <span>Ateneo</span>
          <span className="pie-nota">Marketplace de modelos de IA clínica · pre-MVP</span>
        </div>

        <nav className="pie-enlaces" aria-label="Secciones">
          <Enlace a="/publicar">Publicar modelo</Enlace>
          <Enlace a="/consulta">Consultar estudio</Enlace>
        </nav>

        <div className="pie-datos">
          <EstadoApi salud={salud} consultado={consultado} />
          <span className="pie-nota">Cloud Computing 82.08 · ITBA</span>
        </div>
      </div>
    </footer>
  );
}
