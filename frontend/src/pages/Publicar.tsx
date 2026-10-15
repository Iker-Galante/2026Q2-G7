import { useCallback, useEffect, useMemo, useState } from "react";
import type { ContratoModelo, Modelo } from "../api/tipos";
import CatalogoModelos from "../components/CatalogoModelos";
import ListaDisponibles, { clave } from "../components/ListaDisponibles";
import SubirModelo from "../components/SubirModelo";
import TarjetaEvaluacion from "../components/TarjetaEvaluacion";
import { Enlace } from "../enrutador";
import { useModelos } from "../hooks/useModelos";
import { usePublicacion } from "../hooks/usePublicacion";

/** De dónde salió la publicación en curso, para mostrar el error donde se apretó. */
type Origen = "subida" | "bucket";

/**
 * La vista de quien publica: subir el modelo al bucket, mirar cómo lo mide la
 * instancia aislada y comparar el resultado con el resto del catálogo.
 */
export default function Publicar() {
  const modelos = useModelos();
  const [idSeleccionado, setIdSeleccionado] = useState<string | null>(null);
  const [claveEnCurso, setClaveEnCurso] = useState<string | null>(null);
  const [origen, setOrigen] = useState<Origen>("subida");

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

  const ocupado = useCallback(
    (nombre: string, version: string) =>
      modelos.disponibles.some((m) => m.nombre === nombre && m.version === version),
    [modelos.disponibles],
  );

  const subir = (archivo: File, contrato: ContratoModelo) => {
    setOrigen("subida");
    publicacion.limpiarError();
    void publicacion.subirYPublicar(archivo, contrato);
  };

  const republicar = (nombre: string, version: string) => {
    setOrigen("bucket");
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
          Subí el <code>.onnx</code> y su contrato. El archivo va del navegador directo al bucket
          con una URL prefirmada, sin pasar por la API; después la API valida el contrato, lo
          escribe como <code>modelo.json</code> al lado y deja el pedido en la cola de evaluaciones.
          El evaluador, en la subred aislada, arranca solo (si estaba apagado tarda uno o dos
          minutos) y lo mide contra el conjunto reservado de su tipo de estudio.
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
          <h2>Subir un modelo</h2>
        </div>

        <div className="dos-columnas">
          <SubirModelo
            publicando={publicacion.publicando}
            etapa={publicacion.etapa}
            progreso={publicacion.progreso}
            error={origen === "subida" ? publicacion.error : null}
            ocupado={ocupado}
            onSubir={subir}
            onLimpiarError={publicacion.limpiarError}
          />

          <aside className="nota">
            <h3>Qué pasa cuando apretás subir</h3>
            <ul className="lista-plana">
              <li>
                La API reserva <code>modelos/&lt;nombre&gt;/&lt;version&gt;/</code> y firma la
                subida. Si esa versión ya existe, responde <code>409</code>: no se pisa.
              </li>
              <li>
                El ONNX viaja del navegador a S3 con esa firma, que ata el tamaño máximo y el
                content type.
              </li>
              <li>
                El alta valida el contrato —campos obligatorios, <code>forma</code> de cuatro
                dimensiones con batch 1 coherente con el <code>layout</code> y el espacio de color,
                etiquetas sin repetir, <code>positiva</code> entre ellas—, confirma que el archivo
                llegó y recién ahí escribe el <code>modelo.json</code>.
              </li>
              <li>
                Que los tensores existan en el grafo lo comprueba el evaluador al cargar el ONNX:
                la API no tiene ONNX Runtime.
              </li>
            </ul>
          </aside>
        </div>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">02</span>
          <h2>En el bucket</h2>
        </div>

        <ListaDisponibles
          disponibles={modelos.disponibles}
          cargando={modelos.cargando}
          publicando={publicacion.publicando}
          claveEnCurso={claveEnCurso}
          onPublicar={republicar}
        />

        {origen === "bucket" && publicacion.error && (
          <div className="caja-error" role="alert">
            {publicacion.error}
          </div>
        )}

        <p className="caption">
          Todo lo que ya está en el bucket, sin importar si llegó por acá o lo subió el operador a
          mano. Volver a publicar borra las métricas y lo vuelve a medir; si está pendiente o en
          curso, la API responde <code>409</code> y no pasa nada.
        </p>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">03</span>
          <h2>La evaluación</h2>
        </div>

        {seleccionado ? (
          <TarjetaEvaluacion modelo={seleccionado} />
        ) : (
          <p className="vacio">
            Publicá un modelo y su evaluación aparece acá, de «pendiente» a las métricas, sin
            recargar la página.
          </p>
        )}
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">04</span>
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
