import { useCallback, useEffect, useMemo, useState } from "react";
import type { Modelo } from "../api/tipos";
import CargadorImagen from "../components/CargadorImagen";
import EstadoApi from "../components/EstadoApi";
import EstadoTrabajo from "../components/EstadoTrabajo";
import PanelPublicar from "../components/PanelPublicar";
import ResultadoInferencia from "../components/ResultadoInferencia";
import SelectorModelo from "../components/SelectorModelo";
import TarjetaEvaluacion from "../components/TarjetaEvaluacion";
import { useInferencia } from "../hooks/useInferencia";
import { useModelos } from "../hooks/useModelos";
import { usePublicacion } from "../hooks/usePublicacion";
import { useSalud } from "../hooks/useSalud";

/**
 * Única página: a la izquierda el modelo (elegir, ver evaluación, publicar);
 * a la derecha el estudio (subir imagen, inferir, ver resultado).
 * El único estado compartido entre columnas es el modelo elegido.
 */
export default function Laboratorio() {
  const modelos = useModelos();
  const { salud, consultado } = useSalud();
  const inferencia = useInferencia();

  const [idSeleccionado, setIdSeleccionado] = useState<string | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);

  const modeloSeleccionado: Modelo | null = useMemo(
    () => modelos.publicados.find((m) => m.id === idSeleccionado) ?? null,
    [modelos.publicados, idSeleccionado],
  );

  // Si no hay nada elegido (o lo elegido desapareció), tomamos el más nuevo.
  useEffect(() => {
    if (modelos.publicados.length === 0) return;
    if (idSeleccionado !== null && modelos.publicados.some((m) => m.id === idSeleccionado)) return;
    setIdSeleccionado(modelos.publicados[0].id);
  }, [modelos.publicados, idSeleccionado]);

  const { actualizarModelo, refrescar } = modelos;

  const alPublicar = useCallback(
    (modelo: Modelo) => {
      actualizarModelo(modelo);
      setIdSeleccionado(modelo.id);
      void refrescar();
    },
    [actualizarModelo, refrescar],
  );

  const publicacion = usePublicacion({ alPublicar, alActualizar: actualizarModelo });

  // Si el modelo elegido todavía se está evaluando, seguimos su evaluación.
  const estadoSeleccionado = modeloSeleccionado?.estado_evaluacion ?? null;
  const { seguir } = publicacion;
  useEffect(() => {
    if (idSeleccionado === null) return;
    if (estadoSeleccionado === "pendiente" || estadoSeleccionado === "en_curso") {
      seguir(idSeleccionado);
    }
  }, [idSeleccionado, estadoSeleccionado, seguir]);

  const elegirArchivo = (nuevo: File) => {
    setArchivo(nuevo);
    inferencia.reiniciar();
  };

  const quitarArchivo = () => {
    setArchivo(null);
    inferencia.reiniciar();
  };

  const inferir = () => {
    if (archivo === null || modeloSeleccionado === null || inferencia.enCurso) return;
    void inferencia.ejecutar(archivo, modeloSeleccionado);
  };

  const puedeInferir =
    archivo !== null &&
    modeloSeleccionado !== null &&
    modeloSeleccionado.estado_evaluacion !== "error" &&
    !inferencia.enCurso;

  return (
    <div className="pagina">
      <header className="cabecera">
        <h1>Ateneo · Laboratorio</h1>
        <p className="subtitulo">
          Elegí un modelo clínico publicado, subí un estudio y mirá qué predice.
        </p>
      </header>

      <main className="laboratorio">
        <section className="columna">
          <h2>Modelo</h2>

          {modelos.error && (
            <div className="caja-error" role="alert">
              No se pudieron cargar los modelos: {modelos.error}{" "}
              <button type="button" className="enlace" onClick={() => void modelos.refrescar()}>
                Reintentar
              </button>
            </div>
          )}

          <SelectorModelo
            modelos={modelos.publicados}
            seleccionadoId={idSeleccionado}
            cargando={modelos.cargando}
            deshabilitado={inferencia.enCurso}
            onSeleccionar={(id) => {
              setIdSeleccionado(id);
              inferencia.reiniciar();
            }}
          />

          {modeloSeleccionado && <TarjetaEvaluacion modelo={modeloSeleccionado} />}

          <PanelPublicar
            disponibles={modelos.disponibles}
            publicando={publicacion.publicando}
            error={publicacion.error}
            onPublicar={(nombre, version) => void publicacion.publicar(nombre, version)}
            onLimpiarError={publicacion.limpiarError}
          />
        </section>

        <section className="columna">
          <h2>Estudio</h2>

          <CargadorImagen
            archivo={archivo}
            tipoEstudio={modeloSeleccionado?.tipo_estudio ?? null}
            deshabilitado={inferencia.enCurso}
            onSeleccionar={elegirArchivo}
            onQuitar={quitarArchivo}
          />

          <div className="fila-accion">
            <button type="button" onClick={inferir} disabled={!puedeInferir}>
              {inferencia.enCurso ? "Infiriendo…" : "Inferir"}
            </button>
            {(inferencia.etapa === "ok" || inferencia.etapa === "error") && (
              <button type="button" className="secundario" onClick={inferencia.reiniciar}>
                Nueva inferencia
              </button>
            )}
          </div>
          {modeloSeleccionado === null && modelos.publicados.length > 0 && (
            <p className="ayuda">Elegí un modelo para poder inferir.</p>
          )}

          <EstadoTrabajo etapa={inferencia.etapa} trabajo={inferencia.trabajo} />

          {inferencia.etapa === "error" && inferencia.error && inferencia.trabajo?.estado !== "error" && (
            <div className="caja-error" role="alert">
              {inferencia.error}
            </div>
          )}

          {inferencia.trabajo && (inferencia.etapa === "ok" || inferencia.etapa === "error") && (
            <ResultadoInferencia trabajo={inferencia.trabajo} />
          )}
        </section>
      </main>

      <footer className="pie">
        <EstadoApi salud={salud} consultado={consultado} />
      </footer>
    </div>
  );
}
