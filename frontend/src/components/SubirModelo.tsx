import { useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent } from "react";
import type { ContratoModelo } from "../api/tipos";
import type { EtapaPublicacion } from "../hooks/usePublicacion";
import { PLANTILLA_CONTRATO, leerContrato } from "../utilidades/contrato";
import { tamanoLegible } from "../utilidades/formato";

// El mismo tope que MAX_BYTES_MODELO en el backend.
const TAMANO_MAXIMO = 512 * 1024 * 1024;

interface Props {
  publicando: boolean;
  etapa: EtapaPublicacion;
  progreso: number;
  error: string | null;
  /** ¿Ya hay algo en el bucket con ese nombre y esa versión? */
  ocupado: (nombre: string, version: string) => boolean;
  onSubir: (archivo: File, contrato: ContratoModelo) => void;
  onLimpiarError: () => void;
}

function esOnnx(archivo: File): boolean {
  return archivo.name.toLowerCase().endsWith(".onnx");
}

function esJson(archivo: File): boolean {
  return archivo.name.toLowerCase().endsWith(".json") || archivo.type === "application/json";
}

/**
 * Subir un modelo: el ONNX va del navegador al bucket con una URL prefirmada y
 * el contrato viaja en el pedido de alta. Acepta los dos archivos de una, o el
 * ONNX y un contrato escrito acá.
 */
export default function SubirModelo({
  publicando,
  etapa,
  progreso,
  error,
  ocupado,
  onSubir,
  onLimpiarError,
}: Props) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [texto, setTexto] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [publicado, setPublicado] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  const lectura = useMemo(() => leerContrato(texto), [texto]);
  const destino =
    lectura.contrato !== null ? `modelos/${lectura.nombre}/${lectura.version}/` : null;
  const yaExiste = lectura.contrato !== null && ocupado(lectura.nombre, lectura.version);

  const puedeSubir = archivo !== null && lectura.contrato !== null && !yaExiste && !publicando;

  // Al terminar bien, el formulario queda limpio para el modelo que sigue y
  // deja dicho dónde quedó el anterior.
  const publicabaAntes = useRef(publicando);
  useEffect(() => {
    if (publicabaAntes.current && !publicando && error === null) {
      setPublicado(destino);
      setArchivo(null);
      setTexto("");
      setAviso(null);
    }
    publicabaAntes.current = publicando;
  }, [publicando, error, destino]);

  const recibir = async (lista: FileList | null) => {
    if (publicando || lista === null) return;
    const archivos = Array.from(lista);
    const onnx = archivos.find(esOnnx);
    const json = archivos.find(esJson);
    const problemas: string[] = [];

    if (onnx) {
      setPublicado(null);
      if (onnx.size > TAMANO_MAXIMO) {
        problemas.push(`El modelo pesa ${tamanoLegible(onnx.size)} y el máximo son 512 MB.`);
      } else {
        setArchivo(onnx);
        onLimpiarError();
      }
    }
    if (json) {
      setTexto(await json.text());
      onLimpiarError();
    }
    if (!onnx && !json) {
      problemas.push("Se esperaban un archivo .onnx y, opcionalmente, su modelo.json.");
    }
    setAviso(problemas.length > 0 ? problemas.join(" ") : null);
  };

  const abrirSelector = () => {
    if (!publicando) entrada.current?.click();
  };

  const soltar = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setArrastrando(false);
    void recibir(e.dataTransfer.files);
  };

  const enviar = () => {
    if (!puedeSubir || archivo === null || lectura.contrato === null) return;
    onSubir(archivo, lectura.contrato);
  };

  return (
    <div className="subir-modelo">
      <div
        className={`zona-soltar${arrastrando ? " activa" : ""}${publicando ? " deshabilitada" : ""}`}
        role="button"
        tabIndex={publicando ? -1 : 0}
        aria-disabled={publicando}
        onClick={abrirSelector}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            abrirSelector();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!publicando) setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={soltar}
      >
        <p>
          <strong>Arrastrá el modelo acá</strong> o hacé clic para elegirlo.
        </p>
        <p className="suave">
          El <code>.onnx</code> y, si lo tenés, su <code>modelo.json</code>. Hasta 512 MB.
        </p>
        <input
          ref={entrada}
          type="file"
          accept=".onnx,.json,application/json"
          multiple
          hidden
          disabled={publicando}
          onChange={(e) => {
            void recibir(e.target.files);
            // Permite volver a elegir el mismo archivo.
            e.target.value = "";
          }}
        />
      </div>

      {archivo && (
        <div className="archivo-info">
          <span className="archivo-nombre" title={archivo.name}>
            {archivo.name}
          </span>
          <span className="suave">{tamanoLegible(archivo.size)}</span>
          <button
            type="button"
            className="pildora pildora-borde chica"
            disabled={publicando}
            onClick={() => setArchivo(null)}
          >
            Quitar
          </button>
        </div>
      )}

      {aviso && (
        <div className="caja-error" role="alert">
          {aviso}
        </div>
      )}

      {publicado && (
        <p className="ayuda" role="status">
          <span className="pastilla ok">subido</span> Quedó en <code>{publicado}</code>.
        </p>
      )}

      <div className="campo">
        <div className="campo-cabecera">
          <span className="campo-etiqueta">Contrato · modelo.json</span>
          <button
            type="button"
            className="enlace"
            disabled={publicando}
            onClick={() => {
              setTexto(PLANTILLA_CONTRATO);
              onLimpiarError();
            }}
          >
            Usar la plantilla
          </button>
        </div>
        <textarea
          className="editor"
          spellCheck={false}
          rows={12}
          value={texto}
          disabled={publicando}
          placeholder="Pegá acá el modelo.json, arrastralo con el ONNX, o empezá de la plantilla."
          onChange={(e) => {
            setTexto(e.target.value);
            onLimpiarError();
          }}
        />
      </div>

      {lectura.error && (
        <p className="ayuda contrato-mal">
          <strong>Contrato:</strong> {lectura.error}
        </p>
      )}

      {lectura.contrato && (
        <div className="destino">
          <span className="pastilla ok">contrato leído</span>
          <span className="suave">{lectura.resumen}</span>
          <code>{destino}</code>
        </div>
      )}

      {yaExiste && (
        <div className="caja-error" role="alert">
          Ya hay un modelo en <code>{destino}</code>. Una versión publicada no se pisa: cambiá
          «version» en el contrato.
        </div>
      )}

      <div className="fila-accion">
        <button type="button" className="pildora pildora-oscura" onClick={enviar} disabled={!puedeSubir}>
          {publicando ? "Subiendo…" : "Subir y publicar"}
        </button>
        {!publicando && archivo === null && (
          <span className="ayuda">Elegí el archivo .onnx para poder subir.</span>
        )}
      </div>

      {publicando && (
        <div className="progreso" aria-live="polite">
          <div className="progreso-pista">
            <div
              className="progreso-relleno"
              style={{ width: `${Math.round((etapa === "subiendo" ? progreso : 1) * 100)}%` }}
            />
          </div>
          <p className="ayuda">
            {etapa === "subiendo"
              ? `Subiendo el modelo al bucket… ${Math.round(progreso * 100)} %`
              : "Validando el contrato y dando de alta…"}
          </p>
        </div>
      )}

      {error && (
        <div className="caja-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
