interface Props {
  /** Lado del cuadrado, en px. */
  tamano?: number;
}

/**
 * El símbolo de Ateneo: tres miradas que se superponen y un punto lleno donde
 * coinciden. Es el ateneo clínico —varias voces, un diagnóstico— y también lo
 * que hace la plataforma con varios modelos. Usa currentColor.
 */
export default function Marca({ tamano = 26 }: Props) {
  return (
    <svg
      className="marca"
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="8.6" r="5.9" opacity="0.85" />
      <circle cx="15" cy="14" r="5.9" opacity="0.85" />
      <circle cx="9" cy="14" r="5.9" opacity="0.85" />
      <circle cx="12" cy="12.2" r="2.1" fill="currentColor" stroke="none" />
    </svg>
  );
}
