import { useEffect, useState } from "react";
import Navegacion from "./components/Navegacion";
import PideIngreso from "./components/PideIngreso";
import PieSitio from "./components/PieSitio";
import { useRuta } from "./enrutador";
import type { Ruta } from "./enrutador";
import { useSalud } from "./hooks/useSalud";
import { useSesion } from "./hooks/useSesion";
import { useTema } from "./hooks/useTema";
import Consulta from "./pages/Consulta";
import Inicio from "./pages/Inicio";
import Publicar from "./pages/Publicar";

const TITULOS: Record<Ruta, string> = {
  "/": "Ateneo · Modelos de IA clínica medidos con la misma vara",
  "/publicar": "Publicar un modelo · Ateneo",
  "/consulta": "Consultar un estudio · Ateneo",
};

interface Props {
  /** El login volvió con un error (cancelado, código vencido, state ajeno). */
  errorIngreso: string | null;
}

/**
 * Marco del sitio: barra, la vista de la ruta actual y pie. Con Cognito, las
 * dos secciones piden sesión; la portada no.
 */
export default function App({ errorIngreso }: Props) {
  const ruta = useRuta();
  const { salud, consultado } = useSalud();
  const { tema, alternar } = useTema();
  const { sesion, conLogin } = useSesion();
  const [aviso, setAviso] = useState(errorIngreso);
  const pideIngreso = conLogin && sesion === null;

  useEffect(() => {
    document.title = TITULOS[ruta];
  }, [ruta]);

  return (
    <div className="sitio">
      <Navegacion salud={salud} consultado={consultado} tema={tema} onAlternarTema={alternar} />

      <main className="contenido">
        {aviso && (
          <div className="caja-error aviso-ingreso" role="alert">
            {aviso}{" "}
            <button type="button" className="enlace" onClick={() => setAviso(null)}>
              Cerrar
            </button>
          </div>
        )}
        {ruta === "/publicar" && (pideIngreso ? <PideIngreso ruta={ruta} /> : <Publicar />)}
        {ruta === "/consulta" && (pideIngreso ? <PideIngreso ruta={ruta} /> : <Consulta />)}
        {ruta === "/" && <Inicio />}
      </main>

      <PieSitio salud={salud} consultado={consultado} />
    </div>
  );
}
