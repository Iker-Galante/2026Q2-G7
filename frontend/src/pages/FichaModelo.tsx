import { useEffect } from "react";
import type { CSSProperties } from "react";
import AnalizarEstudio from "../components/AnalizarEstudio";
import EstadoModelo from "../components/EstadoModelo";
import RendimientoModelo from "../components/RendimientoModelo";
import { Enlace } from "../enrutador";
import { useModelo } from "../hooks/useModelo";
import { fechaLocal } from "../utilidades/formato";
import { nombreTipo, tonoDe } from "../utilidades/metricas";

/** La ficha de un modelo: cómo rindió en la evaluación y, al lado, analizar un estudio con él. */
export default function FichaModelo({ id }: { id: string }) {
  const { modelo, cargando, noExiste, error } = useModelo(id);

  useEffect(() => {
    if (modelo) document.title = `${modelo.nombre_visible ?? modelo.nombre} v${modelo.version} · Ateneo`;
  }, [modelo]);

  const volver = (
    <Enlace a="/modelos" className="volver">
      ← Modelos
    </Enlace>
  );

  if (noExiste) {
    return (
      <div className="marco pagina">
        {volver}
        <div className="vacio">
          <p>Ese modelo no está en el catálogo.</p>
        </div>
      </div>
    );
  }

  if (modelo === null) {
    return (
      <div className="marco pagina">
        {volver}
        {error ? (
          <div className="caja-error" role="alert">
            No se pudo cargar el modelo: {error}
          </div>
        ) : (
          <div className="ficha-esqueleto" aria-busy={cargando} />
        )}
      </div>
    );
  }

  return (
    <div className="marco pagina">
      {volver}

      <header className="ficha-cabecera" style={{ "--tono": tonoDe(modelo.tipo_estudio) } as CSSProperties}>
        <div className="ficha-titulo">
          <div className="ficha-etiquetas">
            <span className="chip">{nombreTipo(modelo.tipo_estudio)}</span>
            <EstadoModelo estado={modelo.estado_evaluacion} />
          </div>
          <h1>
            {modelo.nombre_visible ?? modelo.nombre} <span className="version">v{modelo.version}</span>
          </h1>
          <p className="bajada">
            {modelo.tarea} · {modelo.etiquetas.join(", ")}
          </p>
        </div>
        <p className="ficha-fecha suave">Publicado {fechaLocal(modelo.publicado)}</p>
      </header>

      <div className="ficha-cuerpo">
        <section className="panel" aria-labelledby="titulo-rendimiento">
          <header className="panel-cabecera">
            <h2 id="titulo-rendimiento">Evaluación sobre datos reservados</h2>
          </header>
          <RendimientoModelo modelo={modelo} />
        </section>

        <AnalizarEstudio modelo={modelo} />
      </div>
    </div>
  );
}
