import { useEffect } from "react";
import Navegacion from "./components/Navegacion";
import PieSitio from "./components/PieSitio";
import { useRuta } from "./enrutador";
import type { Ruta } from "./enrutador";
import { useSalud } from "./hooks/useSalud";
import { useTema } from "./hooks/useTema";
import Consulta from "./pages/Consulta";
import Inicio from "./pages/Inicio";
import Publicar from "./pages/Publicar";

const TITULOS: Record<Ruta, string> = {
  "/": "Ateneo · Modelos de IA clínica medidos con la misma vara",
  "/publicar": "Publicar un modelo · Ateneo",
  "/consulta": "Consultar un estudio · Ateneo",
};

/** Marco del sitio: barra, la vista de la ruta actual y pie. */
export default function App() {
  const ruta = useRuta();
  const { salud, consultado } = useSalud();
  const { tema, alternar } = useTema();

  useEffect(() => {
    document.title = TITULOS[ruta];
  }, [ruta]);

  return (
    <div className="sitio">
      <Navegacion salud={salud} consultado={consultado} tema={tema} onAlternarTema={alternar} />

      <main className="contenido">
        {ruta === "/publicar" && <Publicar />}
        {ruta === "/consulta" && <Consulta />}
        {ruta === "/" && <Inicio />}
      </main>

      <PieSitio salud={salud} consultado={consultado} />
    </div>
  );
}
