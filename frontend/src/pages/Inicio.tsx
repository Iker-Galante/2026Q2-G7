import { useMemo } from "react";
import { Flecha } from "../components/Navegacion";
import TarjetaModelo from "../components/TarjetaModelo";
import { Enlace } from "../enrutador";
import { useModelos } from "../hooks/useModelos";
import { porcentaje } from "../utilidades/formato";
import { lideres } from "../utilidades/metricas";

const PASOS = [
  {
    titulo: "Publicá",
    texto: "Subí el modelo ONNX y su contrato: entradas, etiquetas y umbral.",
  },
  {
    titulo: "Evaluación a ciegas",
    texto: "Se mide en una red aislada contra casos reservados que nadie ve.",
  },
  {
    titulo: "Analizá",
    texto: "El equipo clínico elige por la medida y analiza sus estudios.",
  },
];

/** Las tres miradas de la marca, en grande, detrás del título. */
function FondoPortada() {
  return (
    <svg className="portada-anillos" viewBox="0 0 600 600" aria-hidden="true" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="1">
        <circle cx="300" cy="215" r="150" />
        <circle cx="375" cy="350" r="150" />
        <circle cx="225" cy="350" r="150" />
        <circle cx="300" cy="305" r="240" opacity="0.35" />
        <circle cx="300" cy="305" r="290" opacity="0.18" />
      </g>
      <circle cx="300" cy="305" r="34" fill="currentColor" opacity="0.9" />
    </svg>
  );
}

export default function Inicio() {
  const { publicados, error } = useModelos();

  const evaluados = publicados.filter((m) => m.estado_evaluacion === "ok" && m.accuracy !== null);
  const mejor = evaluados.reduce<number | null>((max, m) => Math.max(max ?? 0, m.accuracy ?? 0), null);
  const tipos = new Set(publicados.map((m) => m.tipo_estudio)).size;
  const mejores = useMemo(() => lideres(publicados), [publicados]);
  const destacados = [...evaluados].sort((a, b) => (b.accuracy ?? 0) - (a.accuracy ?? 0)).slice(0, 3);

  return (
    <div className="inicio">
      <section className="portada">
        <div className="portada-fondo" aria-hidden="true">
          <FondoPortada />
        </div>

        <h1 className="portada-titulo">
          <span>Ateneo</span>
        </h1>

        <div className="portada-vidrio">
          <div className="vidrio-texto">
            <p className="vidrio-lema">Modelos de IA clínica, evaluados contra casos que nadie vio.</p>
            <div className="acciones">
              <Enlace a="/modelos" className="pildora pildora-clara">
                Explorar modelos <Flecha />
              </Enlace>
              <Enlace a="/publicar" className="pildora pildora-vidrio">
                Publicar un modelo
              </Enlace>
            </div>
          </div>

          {error === null && (
            <dl className="vidrio-datos">
              <div>
                <dt>Modelos</dt>
                <dd>{publicados.length}</dd>
              </div>
              <div>
                <dt>Evaluados</dt>
                <dd>{evaluados.length}</dd>
              </div>
              <div>
                <dt>Tipos de estudio</dt>
                <dd>{tipos}</dd>
              </div>
              <div>
                <dt>Mejor accuracy</dt>
                <dd>{mejor !== null ? porcentaje(mejor) : "—"}</dd>
              </div>
            </dl>
          )}
        </div>
      </section>

      <section className="marco seccion">
        <header className="cabecera-seccion">
          <h2 className="titular">
            IA clínica medida
            <br />
            con la misma vara
          </h2>
        </header>

        {destacados.length > 0 ? (
          <div className="grilla-modelos">
            {destacados.map((m) => (
              <TarjetaModelo key={m.id} modelo={m} mejor={mejores.has(m.id)} />
            ))}
          </div>
        ) : (
          <div className="vacio">
            <p>Todavía no hay modelos evaluados.</p>
          </div>
        )}

        <div className="centrado">
          <Enlace a="/modelos" className="pildora pildora-oscura">
            Ver todos los modelos <Flecha />
          </Enlace>
        </div>
      </section>

      <section className="marco seccion">
        <header className="cabecera-seccion">
          <h2 className="titular">Cómo funciona?</h2>
        </header>

        <ol className="pasos-inicio">
          {PASOS.map((paso, i) => (
            <li key={paso.titulo}>
              <span className="paso-numero">{String(i + 1).padStart(2, "0")}</span>
              <h3>{paso.titulo}</h3>
              <p>{paso.texto}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="marco seccion">
        <div className="banda">
          <div>
            <h2>¿Tenés un modelo?</h2>
            <p>Publicalo y obtené una medida independiente, comparable con el resto del catálogo.</p>
          </div>
          <Enlace a="/publicar" className="pildora pildora-clara">
            Publicar un modelo <Flecha />
          </Enlace>
        </div>
      </section>
    </div>
  );
}
