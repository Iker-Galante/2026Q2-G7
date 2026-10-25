import { crearCuenta, ingresar } from "../api/sesion";
import { Flecha } from "./Navegacion";
import { Enlace } from "../enrutador";

interface Props {
  /** Dentro de otro panel (la ficha): sin encabezado de página. */
  compacto?: boolean;
  texto?: string;
}

/** La puerta a Cognito. La contraseña nunca pasa por Ateneo. */
export default function PideIngreso({ compacto = false, texto }: Props) {
  const acciones = (
    <div className="pide-ingreso">
      <button type="button" className="pildora pildora-oscura" onClick={ingresar}>
        Ingresar <Flecha />
      </button>
      <p className="suave">
        ¿Sin cuenta? Registrate como{" "}
        <button type="button" className="enlace" onClick={() => crearCuenta("publicador")}>
          publicador
        </button>{" "}
        o como{" "}
        <button type="button" className="enlace" onClick={() => crearCuenta("institucion")}>
          institución
        </button>
        .
      </p>
    </div>
  );

  if (compacto) {
    return (
      <div className="ingreso-compacto">
        <p>{texto ?? "Ingresá para continuar."}</p>
        {acciones}
      </div>
    );
  }

  return (
    <div className="marco angosto pagina">
      <header className="cabecera-pagina centrada">
        <h1>Ingresá para publicar</h1>
        <p className="bajada">{texto ?? "Publicar uno propio es opcional y requiere una cuenta de publicador. Podés explorar el catálogo sin publicar un modelo."}</p>
      </header>
      <p className="opcion-catalogo">
        <Enlace a="/modelos">Ver los modelos disponibles</Enlace>
      </p>
      {acciones}
    </div>
  );
}
