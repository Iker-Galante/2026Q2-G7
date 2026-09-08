interface Paso {
  num: string;
  titulo: string;
  sub: [string, string];
  aislada?: boolean;
}

const PASOS: Paso[] = [
  { num: "01", titulo: "Publicador", sub: ["modelo.onnx", "modelo.json"] },
  { num: "02", titulo: "Alta", sub: ["valida el contrato", "queda pendiente"] },
  { num: "03", titulo: "Evaluación", sub: ["conjunto reservado", "sin internet"], aislada: true },
  { num: "04", titulo: "Catálogo", sub: ["accuracy y métricas", "con trazabilidad"] },
  { num: "05", titulo: "Consulta", sub: ["estudio → predicción", "probabilidad por clase"] },
];

const ETIQUETAS = ["sube", "encola", "mide", "elige"];

const ANCHO = 132;
const HUECO = 56;
const X0 = 28;
const CENTRO_Y = 82;

const x = (i: number) => X0 + i * (ANCHO + HUECO);

/** Ancho de la llave que abraza «Evaluación» y «Catálogo». */
const LLAVE = ANCHO + HUECO + ANCHO;

/**
 * El camino de un modelo, de quien lo publica a quien lo consulta. Es el mismo
 * recorrido que describe architecture.md, dibujado para la portada.
 */
export default function DiagramaFlujo() {
  return (
    <div className="figura">
      <svg viewBox="0 0 940 196" className="diagrama" role="img" aria-labelledby="dg-t dg-d">
        <title id="dg-t">Recorrido de un modelo en Ateneo</title>
        <desc id="dg-d">
          El publicador sube el modelo y su contrato; la API lo da de alta; una instancia aislada lo
          mide contra un conjunto reservado; el catálogo publica la accuracy; el equipo clínico elige
          un modelo y consulta un estudio. De la subred aislada solo sale el número.
        </desc>

        <defs>
          <marker id="dg-punta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path className="dg-punta" d="M0 0 10 5 0 10z" />
          </marker>
        </defs>

        {PASOS.map((paso, i) => (
          <g key={paso.num}>
            <text className="dg-num" x={x(i) + ANCHO / 2} y="24" textAnchor="middle">
              {paso.num}
            </text>
            <rect
              className={paso.aislada ? "dg-caja dg-aislada" : "dg-caja"}
              x={x(i)}
              y="36"
              width={ANCHO}
              height="92"
              rx="8"
            />
            <text
              className={paso.aislada ? "dg-t dg-t-senal" : "dg-t"}
              x={x(i) + ANCHO / 2}
              y="70"
              textAnchor="middle"
            >
              {paso.titulo}
            </text>
            <text className="dg-s" x={x(i) + ANCHO / 2} y="92" textAnchor="middle">
              {paso.sub[0]}
            </text>
            <text className="dg-s" x={x(i) + ANCHO / 2} y="108" textAnchor="middle">
              {paso.sub[1]}
            </text>
          </g>
        ))}

        {ETIQUETAS.map((etiqueta, i) => {
          const desde = x(i) + ANCHO;
          const hasta = x(i + 1);
          return (
            <g key={etiqueta}>
              <line
                className="dg-flecha"
                x1={desde + 3}
                y1={CENTRO_Y}
                x2={hasta - 2}
                y2={CENTRO_Y}
                markerEnd="url(#dg-punta)"
              />
              <text className="dg-lbl" x={(desde + hasta) / 2} y={CENTRO_Y - 10} textAnchor="middle">
                {etiqueta}
              </text>
            </g>
          );
        })}

        <path className="dg-llave" d={`M${x(2)} 152v-8M${x(2)} 152h${LLAVE}M${x(2) + LLAVE} 152v-8`} />
        <text className="dg-lbl-senal" x={x(2) + LLAVE / 2} y="172" textAnchor="middle">
          de la subred aislada solo sale el número
        </text>
      </svg>
    </div>
  );
}
