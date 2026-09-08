import { useCallback, useEffect, useMemo, useState } from "react";
import type { Modelo } from "../api/tipos";
import CatalogoModelos from "../components/CatalogoModelos";
import ListaDisponibles, { clave } from "../components/ListaDisponibles";
import TarjetaEvaluacion from "../components/TarjetaEvaluacion";
import { Enlace } from "../enrutador";
import { useModelos } from "../hooks/useModelos";
import { usePublicacion } from "../hooks/usePublicacion";

/**
 * La vista de quien publica: dar de alta un modelo del bucket, mirar cómo lo
 * mide la instancia aislada y comparar el resultado con el resto del catálogo.
 */
export default function Publicar() {
  const modelos = useModelos();
  const [idSeleccionado, setIdSeleccionado] = useState<string | null>(null);
  const [claveEnCurso, setClaveEnCurso] = useState<string | null>(null);

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

  // Sin nada elegido (o si lo elegido desapareció), mostramos el más nuevo.
  useEffect(() => {
    if (modelos.publicados.length === 0) return;
    if (idSeleccionado !== null && modelos.publicados.some((m) => m.id === idSeleccionado)) return;
    setIdSeleccionado(modelos.publicados[0].id);
  }, [modelos.publicados, idSeleccionado]);

  const seleccionado = useMemo(
    () => modelos.publicados.find((m) => m.id === idSeleccionado) ?? null,
    [modelos.publicados, idSeleccionado],
  );

  // Si el modelo que se está mirando todavía se evalúa, seguimos su evaluación.
  const estadoSeleccionado = seleccionado?.estado_evaluacion ?? null;
  const { seguir } = publicacion;
  useEffect(() => {
    if (idSeleccionado === null) return;
    if (estadoSeleccionado === "pendiente" || estadoSeleccionado === "en_curso") {
      seguir(idSeleccionado);
    }
  }, [idSeleccionado, estadoSeleccionado, seguir]);

  // El spinner de la fila vive mientras dura el POST.
  useEffect(() => {
    if (!publicacion.publicando) setClaveEnCurso(null);
  }, [publicacion.publicando]);

  const publicar = (nombre: string, version: string) => {
    setClaveEnCurso(clave({ nombre, version }));
    publicacion.limpiarError();
    void publicacion.publicar(nombre, version);
  };

  return (
    <div className="pagina">
      <header className="encabezado">
        <p className="eyebrow">Para quien publica</p>
        <h1>Publicar un modelo</h1>
        <p className="lede">
          Un modelo es un prefijo del bucket con dos archivos: <code>modelo.onnx</code> y{" "}
          <code>modelo.json</code>. Al darlo de alta, la API valida el contrato y lo deja pendiente;
          la instancia aislada lo toma en los próximos segundos y lo mide contra el conjunto
          reservado de su tipo de estudio.
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
          <h2>En el bucket</h2>
        </div>

        <ListaDisponibles
          disponibles={modelos.disponibles}
          cargando={modelos.cargando}
          publicando={publicacion.publicando}
          claveEnCurso={claveEnCurso}
          onPublicar={publicar}
        />

        {publicacion.error && (
          <div className="caja-error" role="alert">
            {publicacion.error}
          </div>
        )}
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">02</span>
          <h2>La evaluación</h2>
        </div>

        <div className="dos-columnas">
          {seleccionado ? (
            <TarjetaEvaluacion modelo={seleccionado} />
          ) : (
            <p className="vacio">
              Publicá un modelo y su evaluación aparece acá, de «pendiente» a las métricas, sin
              recargar la página.
            </p>
          )}

          <aside className="nota">
            <h3>Qué valida el alta</h3>
            <ul className="lista-plana">
              <li>Campos obligatorios y enums del contrato.</li>
              <li>
                <code>forma</code> de cuatro dimensiones con batch 1, coherente con el{" "}
                <code>layout</code> y con el espacio de color.
              </li>
              <li>
                Etiquetas sin repetir y <code>positiva</code> entre ellas.
              </li>
              <li>
                Que los tensores existan en el grafo lo comprueba el evaluador al cargar el ONNX: la
                API no tiene ONNX Runtime.
              </li>
            </ul>
            <p>
              Volver a publicar borra las métricas y vuelve a medir. Si el modelo está pendiente o en
              curso, la API responde <code>409</code> y no pasa nada.
            </p>
          </aside>
        </div>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">03</span>
          <h2>El catálogo</h2>
        </div>

        <CatalogoModelos
          modelos={modelos.publicados}
          seleccionadoId={idSeleccionado}
          cargando={modelos.cargando}
          onSeleccionar={setIdSeleccionado}
        />

        <p className="caption">
          Dos modelos del mismo tipo de estudio se comparan porque los mide el mismo conjunto, en la
          misma versión, con el mismo código que corre en la consulta. Elegí una fila para ver sus
          métricas completas arriba, o pasá a{" "}
          <Enlace a="/consulta">consultar un estudio</Enlace> con el que más te convenza.
        </p>
      </section>
    </div>
  );
}
