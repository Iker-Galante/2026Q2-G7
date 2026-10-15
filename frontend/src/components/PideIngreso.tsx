import { crearCuenta, ingresar } from "../api/sesion";

const TEXTOS = {
  "/publicar": { eyebrow: "Para quien publica", titulo: "Publicar un modelo" },
  "/consulta": { eyebrow: "Para el equipo clínico", titulo: "Consultar un estudio" },
} as const;

interface Props {
  ruta: keyof typeof TEXTOS;
}

/** Lo que se ve en una sección sin sesión: el mismo encabezado y la puerta a Cognito. */
export default function PideIngreso({ ruta }: Props) {
  const { eyebrow, titulo } = TEXTOS[ruta];
  return (
    <div className="pagina angosta">
      <header className="encabezado">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{titulo}</h1>
        <p className="lede">
          Esta sección pide una cuenta. El ingreso lo resuelve Cognito en su propia pantalla: la
          contraseña nunca pasa por Ateneo.
        </p>
      </header>
      <div className="pide-ingreso">
        <button type="button" onClick={ingresar}>
          Ingresar
        </button>
        <p>
          ¿No tenés cuenta? Creá una de{" "}
          <button type="button" className="enlace" onClick={() => crearCuenta("institucion")}>
            institución
          </button>{" "}
          o de{" "}
          <button type="button" className="enlace" onClick={() => crearCuenta("publicador")}>
            publicador
          </button>
          . Los médicos llegan por invitación de su institución.
        </p>
      </div>
    </div>
  );
}
