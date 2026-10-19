import { useCallback, useEffect, useState } from "react";
import type { ContratoModelo, Modelo } from "../api/tipos";
import ListaDisponibles, { clave } from "../components/ListaDisponibles";
import { Flecha } from "../components/Navegacion";
import SubirModelo from "../components/SubirModelo";
import { Enlace, rutaDeModelo } from "../enrutador";
import { useModelos } from "../hooks/useModelos";
import { usePublicacion } from "../hooks/usePublicacion";

/** De dónde salió la publicación en curso, para mostrar el error donde se apretó. */
type Origen = "subida" | "bucket";

/** La vista de quien publica: subir un modelo nuevo y seguir los que ya subió. */
export default function Publicar() {
  const modelos = useModelos();
  const [claveEnCurso, setClaveEnCurso] = useState<string | null>(null);
  const [origen, setOrigen] = useState<Origen>("subida");
  const [recien, setRecien] = useState<Modelo | null>(null);

  const { actualizarModelo, refrescar } = modelos;

  const alPublicar = useCallback(
    (modelo: Modelo) => {
      actualizarModelo(modelo);
      setRecien(modelo);
      void refrescar();
    },
    [actualizarModelo, refrescar],
  );

  const publicacion = usePublicacion({ alPublicar, alActualizar: actualizarModelo });

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
    setRecien(null);
    publicacion.limpiarError();
    void publicacion.subirYPublicar(archivo, contrato);
  };

  const republicar = (nombre: string, version: string) => {
    setOrigen("bucket");
    setRecien(null);
    setClaveEnCurso(clave({ nombre, version }));
    publicacion.limpiarError();
    void publicacion.publicar(nombre, version);
  };

  return (
    <div className="marco pagina">
      <header className="cabecera-pagina">
        <div>
          <p className="eyebrow">[Publicar]</p>
          <h1>Publicar un modelo</h1>
          <p className="bajada">
            Subí el ONNX y su contrato. Lo evaluamos contra el conjunto reservado de su tipo de
            estudio y entra al catálogo con esa medida.
          </p>
        </div>
      </header>

      {modelos.error && (
        <div className="caja-error" role="alert">
          No se pudieron cargar tus modelos: {modelos.error}{" "}
          <button type="button" className="enlace" onClick={() => void modelos.refrescar()}>
            Reintentar
          </button>
        </div>
      )}

      {recien && (
        <div className="aviso-exito" role="status">
          <span>
            <strong>
              {recien.nombre} v{recien.version}
            </strong>{" "}
            quedó publicado y en cola de evaluación.
          </span>
          <Enlace a={rutaDeModelo(recien.id)} className="pildora pildora-oscura chica">
            Seguir la evaluación <Flecha />
          </Enlace>
        </div>
      )}

      <div className="publicar-cuerpo">
        <section className="panel" aria-labelledby="titulo-nuevo">
          <header className="panel-cabecera">
            <h2 id="titulo-nuevo">Nuevo modelo</h2>
          </header>
          <SubirModelo
            publicando={publicacion.publicando}
            etapa={publicacion.etapa}
            progreso={publicacion.progreso}
            error={origen === "subida" ? publicacion.error : null}
            ocupado={ocupado}
            onSubir={subir}
            onLimpiarError={publicacion.limpiarError}
          />
        </section>

        <section className="panel" aria-labelledby="titulo-tus-modelos">
          <header className="panel-cabecera">
            <h2 id="titulo-tus-modelos">Tus modelos</h2>
          </header>
          <ListaDisponibles
            disponibles={modelos.disponibles}
            publicados={modelos.publicados}
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
        </section>
      </div>
    </div>
  );
}
