interface Props {
  pagina: number;
  paginas: number;
  onCambiar: (pagina: number) => void;
}

/** Anterior · 1 2 3 · Siguiente. No se muestra si entra todo en una página. */
export default function Paginacion({ pagina, paginas, onCambiar }: Props) {
  if (paginas <= 1) return null;
  const numeros = Array.from({ length: paginas }, (_, i) => i + 1);

  return (
    <nav className="paginacion" aria-label="Páginas">
      <button type="button" className="pildora pildora-borde" disabled={pagina <= 1} onClick={() => onCambiar(pagina - 1)}>
        Anterior
      </button>
      <ol>
        {numeros.map((n) => (
          <li key={n}>
            <button
              type="button"
              className={n === pagina ? "pagina-numero actual" : "pagina-numero"}
              aria-current={n === pagina ? "page" : undefined}
              onClick={() => onCambiar(n)}
            >
              {n}
            </button>
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="pildora pildora-borde"
        disabled={pagina >= paginas}
        onClick={() => onCambiar(pagina + 1)}
      >
        Siguiente
      </button>
    </nav>
  );
}
