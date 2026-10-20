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
      <div className="marco pie-interior">
        <div className="pie-marca">
          <Marca tamano={20} />
          <span>Ateneo</span>
        </div>

        <nav className="pie-enlaces" aria-label="Secciones">
          <Enlace a="/modelos">Modelos</Enlace>
          <Enlace a="/publicar">Publicar</Enlace>
        </nav>

        <div className="pie-datos">
          <EstadoApi salud={salud} consultado={consultado} variante="compacto" />
          <span>No es un dispositivo médico</span>
          <span>ITBA · Cloud Computing</span>
        </div>
      </div>
    </footer>
  );
}
