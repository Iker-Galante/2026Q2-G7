import { useEffect, useMemo, useState } from "react";
import type { Modelo } from "../api/tipos";
import CargadorImagen from "../components/CargadorImagen";
import EstadoTrabajo from "../components/EstadoTrabajo";
import ResultadoInferencia from "../components/ResultadoInferencia";
import ResumenMedida from "../components/ResumenMedida";
import SelectorModelo from "../components/SelectorModelo";
import TarjetaEvaluacion from "../components/TarjetaEvaluacion";
import { Enlace } from "../enrutador";
import { useInferencia } from "../hooks/useInferencia";
import { useModelos } from "../hooks/useModelos";

/**
 * La vista del equipo clínico: elegir un modelo medido, subir un estudio y
 * leer la predicción junto al número que la pone en contexto.
 */
export default function Consulta() {
  const modelos = useModelos();
  const inferencia = useInferencia();

  const [idSeleccionado, setIdSeleccionado] = useState<string | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);

  const seleccionado: Modelo | null = useMemo(
    () => modelos.publicados.find((m) => m.id === idSeleccionado) ?? null,
    [modelos.publicados, idSeleccionado],
  );

  // Si no hay nada elegido (o lo elegido desapareció), tomamos el más nuevo.
  useEffect(() => {
    if (modelos.publicados.length === 0) return;
    if (idSeleccionado !== null && modelos.publicados.some((m) => m.id === idSeleccionado)) return;
    setIdSeleccionado(modelos.publicados[0].id);
  }, [modelos.publicados, idSeleccionado]);

  const elegirModelo = (id: string) => {
    setIdSeleccionado(id);
    inferencia.reiniciar();
  };

  const elegirArchivo = (nuevo: File) => {
    setArchivo(nuevo);
    inferencia.reiniciar();
  };

  const quitarArchivo = () => {
    setArchivo(null);
    inferencia.reiniciar();
  };

  const evaluacionFallida = seleccionado?.estado_evaluacion === "error";

  const puedeInferir =
    archivo !== null && seleccionado !== null && !evaluacionFallida && !inferencia.enCurso;

  const inferir = () => {
    if (!puedeInferir || archivo === null || seleccionado === null) return;
    void inferencia.ejecutar(archivo, seleccionado);
  };

  return (
    <div className="pagina angosta">
      <header className="encabezado">
        <p className="eyebrow">Para el equipo clínico</p>
        <h1>Consultar un estudio</h1>
        <p className="lede">
          Elegí un modelo del catálogo sabiendo contra qué se midió, subí la imagen y esperá la
          predicción. El estudio va directo a un bucket privado con una URL prefirmada, lo procesa
          una instancia sin salida a internet y se borra solo a los siete días.
        </p>
      </header>

      {modelos.error && (
        <div className="caja-error" role="alert">
          No se pudieron cargar los modelos: {modelos.error}{" "}
          <button type="button" className="enlace" onClick={() => void modelos.refrescar()}>
            Reintentar
          </button>
        </div>
      )}

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">01</span>
          <h2>El modelo</h2>
        </div>

        <SelectorModelo
          modelos={modelos.publicados}
          seleccionadoId={idSeleccionado}
          cargando={modelos.cargando}
          deshabilitado={inferencia.enCurso}
          onSeleccionar={elegirModelo}
        />

        {seleccionado && (
          <>
            <ResumenMedida modelo={seleccionado} />
            <details className="detalle">
              <summary>Ver la evaluación completa</summary>
              <TarjetaEvaluacion modelo={seleccionado} />
            </details>
          </>
        )}

        {evaluacionFallida && (
          <div className="caja-error" role="alert">
            La evaluación de este modelo falló, así que no se puede consultar con él. Elegí otro o
            volvé a publicarlo desde <Enlace a="/publicar">la sección de publicación</Enlace>.
          </div>
        )}
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">02</span>
          <h2>El estudio</h2>
        </div>

        <CargadorImagen
          archivo={archivo}
          tipoEstudio={seleccionado?.tipo_estudio ?? null}
          deshabilitado={inferencia.enCurso}
          onSeleccionar={elegirArchivo}
          onQuitar={quitarArchivo}
        />

        <div className="fila-accion">
          <button type="button" onClick={inferir} disabled={!puedeInferir}>
            {inferencia.enCurso ? "Consultando…" : "Consultar"}
          </button>
          {(inferencia.etapa === "ok" || inferencia.etapa === "error") && (
            <button type="button" className="secundario" onClick={inferencia.reiniciar}>
              Otra consulta
            </button>
          )}
          {seleccionado === null && modelos.publicados.length > 0 && (
            <span className="ayuda">Elegí un modelo para poder consultar.</span>
          )}
        </div>

        <EstadoTrabajo etapa={inferencia.etapa} trabajo={inferencia.trabajo} />
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">03</span>
          <h2>El resultado</h2>
        </div>

        {inferencia.etapa === "error" && inferencia.error && inferencia.trabajo?.estado !== "error" && (
          <div className="caja-error" role="alert">
            {inferencia.error}
          </div>
        )}

        {inferencia.trabajo && (inferencia.etapa === "ok" || inferencia.etapa === "error") ? (
          <ResultadoInferencia trabajo={inferencia.trabajo} />
        ) : (
          <p className="vacio">
            Acá aparece la etiqueta predicha, la probabilidad de cada clase, la instancia que la
            calculó y cuánto tardó.
          </p>
        )}

        <div className="aviso">
          <p>
            <strong>Orientativo.</strong> Ateneo no es un dispositivo médico ni reemplaza el criterio
            clínico: muestra qué predice un modelo y con qué precisión se midió, para que la decisión
            la tome una persona.
          </p>
        </div>
      </section>
    </div>
  );
}
