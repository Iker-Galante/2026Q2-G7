import DiagramaFlujo from "../components/DiagramaFlujo";
import { Enlace } from "../enrutador";
import { useModelos } from "../hooks/useModelos";
import { porcentaje } from "../utilidades/formato";

const COMO_FUNCIONA = [
  {
    titulo: "Se publica con un contrato",
    texto:
      "Un modelo es un ONNX más un modelo.json que declara cómo se lo alimenta y cómo se lee su salida: layout, tamaño, normalización, etiquetas y umbral. Sin ese contrato no entra al catálogo, porque un contrato mal escrito no da error: da predicciones malas.",
  },
  {
    titulo: "Se mide donde nadie lo ve",
    texto:
      "Una instancia sin salida a internet, a la que nadie puede iniciar una conexión, corre el modelo contra un conjunto reservado congelado por versión. Quien publica no puede ajustar contra ese conjunto porque no lo tiene.",
  },
  {
    titulo: "Se consulta con el número a la vista",
    texto:
      "El equipo clínico elige un modelo del catálogo sabiendo contra qué se midió, sube un estudio y recibe la etiqueta, la probabilidad de cada clase, qué instancia la calculó y cuánto tardó.",
  },
];

const GARANTIAS = [
  {
    titulo: "El mismo código que en la consulta",
    texto:
      "Evaluador y motor de inferencia comparten el preprocesamiento, el motor ONNX y el posprocesamiento. La accuracy publicada mide exactamente lo que recibe quien consulta, no una versión de laboratorio.",
  },
  {
    titulo: "Conjunto reservado e inmutable",
    texto:
      "Cada evaluación queda atada a un conjunto, una versión y el hash de su manifiesto. Agregar casos crea otra versión: la historia no se reescribe y dos modelos se comparan contra lo mismo.",
  },
  {
    titulo: "Los casos nunca salen de su subred",
    texto:
      "La instancia que evalúa llega a los datos por un endpoint privado y no tiene ruta hacia afuera. Lo único que cruza la frontera es el número que termina en el catálogo.",
  },
];

const LIMITES = [
  "El archivo ONNX se sube a mano al bucket; el botón «Publicar» lo da de alta y dispara la evaluación.",
  "No hay cuentas ni permisos: las dos secciones son dos vistas del mismo sistema, no dos roles.",
  "La junta de varios modelos, el conector del centro de salud y DICOM están diseñados, no implementados.",
  "No es un dispositivo médico: nada de lo que se muestra acá reemplaza un diagnóstico.",
];

export default function Inicio() {
  const { publicados, disponibles, cargando, error } = useModelos();

  const evaluados = publicados.filter((m) => m.estado_evaluacion === "ok" && m.accuracy !== null);
  const mejor = evaluados.reduce<number | null>(
    (max, m) => (max === null || (m.accuracy ?? 0) > max ? (m.accuracy ?? max) : max),
    null,
  );
  const tipos = new Set(publicados.map((m) => m.tipo_estudio));
  const sinPublicar = disponibles.filter((m) => !m.publicado).length;

  return (
    <div className="inicio">
      <section className="portada">
        <div className="portada-texto">
          <p className="eyebrow">Marketplace de modelos de IA clínica</p>
          <h1>Un ateneo clínico para modelos de IA</h1>
          <p className="lede">
            Quien publica un modelo lo somete a un conjunto de casos reservado que nunca ve. Quien
            atiende elige entre modelos medidos con la misma vara, sube un estudio y recibe una
            predicción con su probabilidad. El nombre viene del ateneo clínico: la reunión donde
            varias voces discuten un caso hasta converger en un diagnóstico.
          </p>

          <div className="portada-acciones">
            <Enlace a="/publicar" className="boton">
              Publicar un modelo
            </Enlace>
            <Enlace a="/consulta" className="boton boton-suave">
              Consultar un estudio
            </Enlace>
          </div>

          {error !== null ? (
            <p className="tira-vacia">
              No se pudo consultar el catálogo ahora mismo. Las dos secciones siguen ahí y vuelven a
              intentarlo.
            </p>
          ) : (
            <dl className="tira" aria-busy={cargando}>
              <div>
                <dt>Modelos publicados</dt>
                <dd>{publicados.length}</dd>
              </div>
              <div>
                <dt>Evaluados</dt>
                <dd>{evaluados.length}</dd>
              </div>
              <div>
                <dt>Mejor accuracy</dt>
                <dd>{mejor !== null ? porcentaje(mejor) : "—"}</dd>
              </div>
              <div>
                <dt>Tipos de estudio</dt>
                <dd>{tipos.size}</dd>
              </div>
              <div>
                <dt>En el bucket sin publicar</dt>
                <dd>{sinPublicar}</dd>
              </div>
            </dl>
          )}
        </div>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">01</span>
          <h2>El recorrido</h2>
        </div>
        <DiagramaFlujo />
        <p className="caption">
          Cinco pasos y una frontera. Publicar y consultar pasan por la capa de aplicación; medir
          pasa por una subred aislada de la que sale un número y nada más.
        </p>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">02</span>
          <h2>Cómo funciona</h2>
        </div>
        <ol className="pasos-num">
          {COMO_FUNCIONA.map((paso) => (
            <li key={paso.titulo}>
              <h3>{paso.titulo}</h3>
              <p>{paso.texto}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">03</span>
          <h2>Dos puertas</h2>
        </div>
        <div className="puertas">
          <article className="puerta">
            <p className="eyebrow">Para quien publica</p>
            <h3>Publicar un modelo</h3>
            <p>
              Dale de alta un modelo del bucket, seguí su evaluación mientras corre y compará su
              accuracy con el resto del catálogo contra el mismo conjunto de casos.
            </p>
            <ul className="lista-marcas">
              <li>Alta y re-publicación con validación del contrato</li>
              <li>Evaluación en vivo, de «pendiente» a las métricas</li>
              <li>Matriz de confusión, sensibilidad, especificidad y AUC</li>
              <li>Catálogo comparable por tipo de estudio</li>
            </ul>
            <Enlace a="/publicar" className="boton">
              Entrar a publicación
            </Enlace>
          </article>

          <article className="puerta">
            <p className="eyebrow">Para el equipo clínico</p>
            <h3>Consultar un estudio</h3>
            <p>
              Elegí un modelo evaluado, subí la imagen y recibí la predicción con su probabilidad,
              la instancia que la atendió y el tiempo que tardó.
            </p>
            <ul className="lista-marcas">
              <li>Modelos con su accuracy y su conjunto a la vista</li>
              <li>PNG o JPEG hasta 20 MB, directo a un bucket privado</li>
              <li>Seguimiento del trabajo paso a paso, con reintentos</li>
              <li>El estudio se borra solo a los 7 días</li>
            </ul>
            <Enlace a="/consulta" className="boton boton-suave">
              Entrar a consulta
            </Enlace>
          </article>
        </div>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">04</span>
          <h2>Por qué el número significa algo</h2>
        </div>
        <div className="garantias">
          {GARANTIAS.map((g) => (
            <article key={g.titulo} className="garantia">
              <h3>{g.titulo}</h3>
              <p>{g.texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="seccion">
        <div className="sechead">
          <span className="secnum">05</span>
          <h2>Lo que todavía no hace</h2>
        </div>
        <div className="aviso">
          <p>
            Esto es un pre-MVP: demuestra los dos caminos de la arquitectura de punta a punta y no
            esconde lo que le falta.
          </p>
          <ul className="lista-plana">
            {LIMITES.map((limite) => (
              <li key={limite}>{limite}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
