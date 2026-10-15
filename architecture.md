# Ateneo · Arquitectura de la aplicación

> Estado: borrador 2 · 2026-09-07
> Complementa a [specs.md](specs.md) (qué hace) y a los documentos de infraestructura
> (`ateneo-en-aws.html`, `ateneo-paso-a-paso.html`). Este documento dice **cómo está construido el
> código** para que entre en esa infraestructura sin tocarla y para que crezca sin reescribirse.

---

## 1. Componentes y dónde corren

| Componente | Repo | Capa de red | Cómo llega | Proceso |
|------------|------|-------------|------------|---------|
| Frontend | `frontend/` | S3 `ateneo-web` → copiado a cada instancia app al arrancar | `npm run build` · `aws s3 sync dist/` · `refrescar.sh asg-app` | lo sirve el backend en `/` |
| Backend (API + despachador) | `backend/` | app (`asg-app`, `t3.small`) | `backend-latest.zip` → user data de `lt-app` | `uvicorn app.main:app :8080 --workers 2` |
| Worker | `worker/` + `ateneo_ml/` | inferencia (`asg-inf`, `c5.large`, sin internet) | `worker-latest.zip` → AMI dorada + user data de `lt-worker` | `uvicorn worker.main:app :8081` |
| Evaluador | `evaluador/` + `ateneo_ml/` | evaluación (`eval-1`, `c5.large`, aislada) | mismo `worker-latest.zip` → `lt-eval` | `python -m evaluador.main` |
| Migraciones | `migraciones/` | se aplican desde una instancia app | `psql -f` por Session Manager | — |
| Herramientas | `tools/` | tu máquina / CloudShell | no se despliegan | — |

```
                                ┌──────────────────────────────┐
 navegador ── http://<alb> ────►│ ALB → backend (capa app)     │
   │  GET /  (sitio estático)   │  · API  /api/*               │   8081   ┌──────────────────┐
   │  /api/* (JSON)             │  · despachador (tarea fondo) ├─────────►│ ALB int → worker │
   │                            └────────┬───────────┬─────────┘          └───┬──────────┬───┘
   │ POST prefirmado                     │           │                        │          │
   ▼                                     ▼           ▼                        ▼          ▼
 S3 estudios ◄──────────────────── Postgres      S3 modelos ──────────────► EFS (caché)
                                        ▲
                             poll 10 s  │  UPDATE modelo (accuracy, metricas)
                           ┌────────────┴─────────────┐
                           │ evaluador (eval-1)       │──► S3 evaluación (solo por vpce)
                           └──────────────────────────┘──► S3 modelos
```

Las flechas son exactamente las que los security groups permiten (§03 de la guía). No hay ninguna
otra: **nadie llama al evaluador**, **el worker no toca la base**, y **el navegador solo habla con
el ALB y con S3**.

## 2. Estructura del repositorio

```
TP-AWS/
├── specs.md · architecture.md · README.md
├── backend/                     # FastAPI · capa app
│   ├── app/
│   │   ├── main.py              # crea la app, monta el sitio en "/", arranca el despachador (lifespan)
│   │   ├── config.py            # Settings (pydantic-settings) desde variables de entorno
│   │   ├── dominio/             # entidades y reglas puras; sin FastAPI, sin boto3, sin SQL
│   │   │   ├── modelo.py · estudio.py · trabajo.py
│   │   │   ├── contrato.py      # validación de modelo.json (misma que ateneo_ml, ver §7)
│   │   │   └── errores.py       # NoEncontrado, Conflicto, EntradaInvalida, ServicioNoDisponible
│   │   ├── aplicacion/          # casos de uso; dependen solo de puertos
│   │   │   ├── puertos.py       # Protocols: repositorios, almacenes, cliente de inferencia, reloj
│   │   │   ├── casos_uso/
│   │   │   │   ├── listar_modelos_disponibles.py · preparar_subida_modelo.py · publicar_modelo.py
│   │   │   │   ├── consultar_modelo.py · crear_estudio.py · encolar_inferencia.py · consultar_trabajo.py
│   │   │   │   └── despachar_trabajo.py          # lo usa el despachador, no la API
│   │   │   └── despachador.py   # bucle: tomar pendiente → DespacharTrabajo → dormir
│   │   ├── infraestructura/     # adaptadores; uno por tecnología
│   │   │   ├── postgres/        # pool psycopg 3 · repositorios con SQL explícito
│   │   │   ├── s3/              # almacén de estudios (prefirmado) · catálogo de modelos en S3
│   │   │   └── http/            # cliente del ALB interno (httpx, timeout)
│   │   └── api/                 # FastAPI: routers, esquemas pydantic, dependencias (DI), errores, sitio
│   │       ├── dependencias.py · esquemas.py · errores.py · sitio.py
│   │       └── rutas/ salud.py · modelos.py · estudios.py · inferencias.py · trabajos.py
│   ├── tests/
│   └── requirements.txt
├── ateneo_ml/                   # compartido worker + evaluador · SOLO numpy, pillow, onnxruntime
│   ├── contrato.py              # ContratoModelo (dataclass) + parse/validación de modelo.json
│   ├── decodificadores.py       # DecodificadorImagen (Protocol) · Pillow · (Dicom después)
│   ├── preprocesamiento.py      # imagen → tensor según el contrato (layout, color, escala, media/desvío)
│   ├── motor.py                 # Motor (Protocol) · OnnxMotor
│   ├── postprocesamiento.py     # salida cruda → {etiqueta: p} + predicción
│   └── metricas.py              # accuracy, matriz, macro, binarias (numpy)
├── worker/                      # FastAPI · capa inferencia
│   ├── main.py · config.py · aplicacion.py · puertos.py
│   └── infraestructura/ proveedor_efs_s3.py · fuente_s3.py
├── evaluador/                   # proceso largo · eval-1
│   ├── main.py · config.py · aplicacion.py · puertos.py
│   └── infraestructura/ cola_postgres.py · conjunto_s3.py · modelo_s3.py
├── frontend/                    # React + Vite + TypeScript
│   └── src/ api/ · hooks/ · enrutador.tsx · components/ · pages/ · estilos/
├── migraciones/ 001_inicial.sql
├── infra/                       # user data, .env.example, refrescar.sh, apagar.sh, prender.sh, placeholders/
├── tools/                       # descargar_modelo · verificar_modelo · preparar_conjunto · subir_conjunto · migrar
├── docker/                      # Dockerfile.backend · Dockerfile.worker (imagen dorada) · Dockerfile.tests
├── docker-compose.yml           # Postgres 16 + MinIO para desarrollo local
└── .github/workflows/ci.yml     # lint + tests + import-linter
```

**Por qué `ateneo_ml` es un paquete aparte.** La accuracy que escribe el evaluador solo mide lo que
el usuario recibe si los dos corren el mismo preprocesamiento, el mismo motor y el mismo
posprocesamiento. Un paquete compartido lo garantiza por construcción. El backend **no** lo
importa: no tiene ONNX Runtime y no lo necesita.

**Un cambio a la guía.** El zip del worker pasa a incluir el paquete compartido:

```bash
zip -r /tmp/worker-latest.zip worker/ evaluador/ ateneo_ml/ -x "*/__pycache__/*" "*.pyc"
```

Los `ExecStart` de systemd no cambian: `worker.main:app` y `evaluador.main` siguen existiendo, y
los tres paquetes quedan como hermanos en `/opt/worker`, que es el `WorkingDirectory`.

## 3. Principios de diseño

### 3.1 Puertos y adaptadores en cada servicio

```
   api / main / despachador  ──►  aplicacion (casos de uso)  ──►  dominio
              │                              ▲
              └──────── infraestructura ─────┘   (los adaptadores implementan los puertos)
```

- **Dominio**: dataclasses y reglas (`Trabajo.marcar_ok(...)`, `Trabajo.marcar_fallido(...)` que
  decide si vuelve a `pendiente` o pasa a `error`, `Modelo.acepta(estudio)`,
  `Modelo.republicar()`). Sin imports de frameworks.
- **Aplicación**: un caso de uso por archivo, una clase con `ejecutar(...)`. Recibe puertos por
  constructor. No sabe si detrás hay S3 o MinIO, Postgres o un dict.
- **Puertos**: `typing.Protocol`, chicos, con nombre de negocio (`AlmacenEstudios`, no `S3Client`).
- **Infraestructura**: único lugar con `boto3`, `psycopg`, `httpx`, `onnxruntime`.
- **API / main / despachador**: traducen (HTTP o reloj) ↔ casos de uso. `main.py` y
  `dependencias.py` son el *composition root*: lo único que instancia adaptadores.

### 3.2 SOLID, con el ejemplo concreto de este código

| Principio | Cómo se ve acá | Qué evita |
|-----------|----------------|-----------|
| **S** · Responsabilidad única | `EncolarInferencia` solo valida e inserta; `DespacharTrabajo` solo lleva un trabajo al worker y guarda; el worker solo infiere; el evaluador solo evalúa. El worker no escribe en la base y la API no llama al worker. | Un `main.py` con SQL, boto3, httpx y reglas mezcladas. |
| **O** · Abierto/cerrado | Un modelo nuevo con otro tamaño, layout NCHW u otra normalización **no cambia código**: cambia `modelo.json`. Un formato de imagen nuevo es un `DecodificadorImagen` registrado por extensión; una tarea nueva (`segmentacion`) es un posprocesador y un calculador de métricas más. | `if modelo == "neumonia": … elif …` |
| **L** · Sustitución de Liskov | Todos los adaptadores de un puerto cumplen el contrato **incluyendo los errores**: un objeto que no existe lanza `NoEncontrado` en S3, en MinIO y en el fake de memoria. | Tests que pasan con el fake y fallan en AWS. |
| **I** · Segregación de interfaces | `ClienteInferencia` tiene un solo método. `ColaTrabajos` tiene `tomar_pendiente()` y `guardar()`; `ColaModelos` tiene `tomar_pendiente()`, `terminar_ok()`, `terminar_error()`, `reencolar_en_curso()`. Ningún caso de uso recibe métodos que no usa. | Un `Repositorio` gigante. |
| **D** · Inversión de dependencias | Casos de uso y adaptadores importan `puertos.py`; **nadie importa `infraestructura` salvo `main.py` y `dependencias.py`**. Lo verifica `import-linter` en CI. | Cambiar de psycopg a SQLAlchemy tocando casos de uso. |

Reglas adicionales:

- **Errores del dominio, no de la tecnología.** Los adaptadores traducen (`ClientError 404` →
  `NoEncontrado`; `httpx.TimeoutException` → `ServicioNoDisponible`). Un solo `exception_handler`
  los convierte en HTTP. Los routers no tienen `try/except`.
- **Los casos de uso devuelven entidades**; la API las convierte a esquemas pydantic.
- **Configuración inmutable y tipada** (`Settings`), cargada una vez e inyectada.
- **Identidad y tiempo inyectados** (`Reloj`, `GeneradorIds`) para tests deterministas.

## 4. Backend

### 4.1 Puertos (`backend/app/aplicacion/puertos.py`)

```python
class RepositorioModelos(Protocol):
    def guardar(self, m: Modelo) -> None: ...                 # insert o update por (nombre, version)
    def obtener(self, id: UUID) -> Modelo: ...                # NoEncontrado
    def buscar(self, nombre: str, version: str) -> Modelo | None: ...
    def listar(self) -> list[Modelo]: ...

class RepositorioEstudios(Protocol):
    def guardar(self, e: Estudio) -> None: ...
    def obtener(self, id: UUID) -> Estudio: ...

class RepositorioTrabajos(Protocol):
    def guardar(self, t: Trabajo) -> None: ...
    def obtener(self, id: UUID) -> Trabajo: ...

class ColaTrabajos(Protocol):                                 # la usa solo el despachador
    def tomar_pendiente(self) -> Trabajo | None: ...          # SKIP LOCKED + estado=en_curso, atómico

class AlmacenEstudios(Protocol):
    def firmar_subida(self, key: str, content_type: str, max_bytes: int) -> SubidaFirmada: ...
    def describir(self, key: str) -> ObjetoAlmacenado: ...    # NoEncontrado si no se subió

class CatalogoModelosEnBucket(Protocol):
    def listar(self) -> list[RefModelo]: ...                  # prefijos con modelo.json
    def leer_contrato(self, prefix: str) -> dict: ...         # NoEncontrado
    def existe(self, prefix: str) -> bool: ...                # una versión no se pisa
    def firmar_subida(self, prefix: str, max_bytes: int) -> SubidaFirmada: ...   # el ONNX
    def describir_modelo(self, prefix: str) -> ObjetoAlmacenado: ...             # NoEncontrado
    def escribir_contrato(self, prefix: str, contrato: dict) -> None: ...

class ClienteInferencia(Protocol):
    def inferir(self, p: PeticionInferencia) -> ResultadoInferencia: ...  # ServicioNoDisponible

class Reloj(Protocol):
    def ahora(self) -> datetime: ...
```

### 4.2 Los casos de uso que importan

```python
class PrepararSubidaModelo:
    def ejecutar(self, nombre: str, version: str, tamano_bytes: int) -> SubidaModelo:
        if self.catalogo.existe(prefix(nombre, version)):                   # Conflicto → 409
            raise Conflicto("una versión publicada no se pisa")             # el ONNX no pasa por acá:
        return SubidaModelo(prefix, self.catalogo.firmar_subida(prefix, self.max_bytes))   # va directo a S3

class PublicarModelo:
    def ejecutar(self, nombre: str, version: str, contrato_crudo: dict | None = None) -> Modelo:
        crudo = contrato_crudo if contrato_crudo is not None else self.catalogo.leer_contrato(prefix)
        contrato = ContratoModelo.desde_json(crudo)                         # EntradaInvalida → 422
        existente = self.modelos.buscar(nombre, version)
        modelo = existente.republicar(contrato, ahora) if existente else Modelo.publicar(contrato, prefix, ahora)
        # republicar(): Conflicto si está pendiente/en_curso; si no, vuelve a pendiente y borra métricas.
        # Va antes de tocar S3: es lo único que puede rechazar el pedido.
        if contrato_crudo is not None:                                      # recién subido desde la web
            self.catalogo.describir_modelo(prefix)                          # NoEncontrado → 404: ¿llegó el ONNX?
            self.catalogo.escribir_contrato(prefix, contrato_crudo)         # el modelo.json nunca queda solo
        self.modelos.guardar(modelo)
        return modelo

class EncolarInferencia:
    def ejecutar(self, estudio_id: UUID, modelo_id: UUID) -> Trabajo:
        estudio, modelo = self.estudios.obtener(estudio_id), self.modelos.obtener(modelo_id)
        if estudio.estado != "subido":
            estudio.confirmar(self.almacen.describir(estudio.s3_key))       # NoEncontrado → 409
            self.estudios.guardar(estudio)
        modelo.verificar_compatible(estudio)                                # EntradaInvalida → 422
        trabajo = Trabajo.nuevo(estudio, modelo, self.reloj.ahora())        # pendiente
        self.trabajos.guardar(trabajo)
        return trabajo

class DespacharTrabajo:
    def ejecutar(self, trabajo: Trabajo) -> None:                           # ya viene en_curso
        modelo, estudio = self.modelos.obtener(trabajo.modelo_id), self.estudios.obtener(trabajo.estudio_id)
        try:
            r = self.cliente.inferir(PeticionInferencia.de(trabajo, modelo, estudio, self.config))
            trabajo.marcar_ok(r, self.reloj.ahora())
        except ServicioNoDisponible as e:
            trabajo.marcar_fallido(str(e), self.reloj.ahora(), max_intentos=self.config.max_intentos)
        self.trabajos.guardar(trabajo)
```

Cada decisión de negocio vive en el dominio (`republicar`, `confirmar`, `verificar_compatible`,
`marcar_fallido` con la regla de los 3 intentos); los casos de uso solo ordenan llamadas. Con fakes
en memoria se prueban en milisegundos.

### 4.3 El despachador

Es la "cola" hecha código, tal cual la §12 de la guía, y **no toca la infraestructura**: usa la
tabla `trabajo` y el ALB interno que ya existen.

```python
# backend/app/aplicacion/despachador.py
class Despachador:
    async def correr(self, detener: asyncio.Event):
        while not detener.is_set():
            trabajo = await asyncio.to_thread(self.cola.tomar_pendiente)
            if trabajo is None:
                await asyncio.wait([detener.wait()], timeout=self.intervalo)   # 1 s
                continue
            await asyncio.to_thread(self.despachar.ejecutar, trabajo)
```

- Arranca en el `lifespan` de FastAPI, uno por proceso de uvicorn. Con 2 instancias × 2 workers hay
  4 despachadores compitiendo por la misma tabla; `SKIP LOCKED` garantiza que un trabajo lo toma
  uno solo. Es una consecuencia deseable: el despacho escala con la capa app.
- `tomar_pendiente` es una sola sentencia atómica:

  ```sql
  update trabajo set estado='en_curso', actualizado=now()
   where id = (select id from trabajo
               where estado='pendiente' and intentos < %(max)s
               order by actualizado for update skip locked limit 1)
   returning *;
  ```

- **Trabajos huérfanos.** Si un proceso muere con un trabajo `en_curso`, nadie lo retoma. El mismo
  bucle, cada minuto, devuelve a `pendiente` los `en_curso` con más de 2 minutos sin actualizar
  (`intentos + 1`). Cubre el reemplazo de instancias de `refrescar.sh`.
- Concurrencia por proceso: 1 trabajo a la vez. Alcanza para la demo; subirla es un semáforo.
- Se apaga limpio: `lifespan` pone el evento y espera al bucle antes de cerrar el pool.

### 4.4 Persistencia

- `psycopg 3` + `psycopg_pool.ConnectionPool` (mín 1, máx 4 por proceso; `db.t3.micro` admite
  ~80 conexiones).
- SQL explícito en los repositorios, `row_factory=dict_row`, mapeo a dataclasses en un solo lugar
  por tabla. Sin ORM (D11).
- Una transacción por caso de uso; en la API la abre la dependencia que entrega la conexión; en
  el despachador, `tomar_pendiente` y `guardar` son transacciones separadas a propósito (la
  llamada al worker de hasta 30 s no puede quedar dentro de una transacción abierta).
- Migraciones: SQL numerado + `tools/migrar.py` (tabla `migracion_aplicada`).

### 4.5 API y sitio estático

- Routers por recurso; reciben casos de uso por `Depends`. `dependencias.py` es el único módulo
  que importa `infraestructura`.
- `errores.py`: `NoEncontrado` 404, `Conflicto` 409, `EntradaInvalida` 422,
  `ServicioNoDisponible` 502.
- `sitio.py`: monta `StaticFiles(directory=WEB_DIR, html=True)` en `/` **después** de los routers
  (lo que se monta en `/` atrapa todo lo demás), y registra un manejador de `404` que fuera de
  `/api` devuelve `index.html`. Si `WEB_DIR` no existe (local sin build), no monta nada.
- `GET /health` sin dependencias ni base; `GET /api/health` agrega `socket.gethostname()`.
- Sin CORS en el backend. En local, sitio y API comparten origen; en AWS con Terraform el sitio
  está en S3 y la API detrás de API Gateway, que es quien contesta el CORS. El de los dos buckets
  a los que el navegador sube directo —estudios y modelos—, para el `POST` prefirmado (guía §04 y
  §10). `infra/cors.sh <origen>` lo aplica a los dos.
- **Las dos subidas son la misma pieza.** La imagen del estudio y el ONNX del modelo salen del
  navegador hacia S3 con un `presigned POST` firmado por la API, que ata el content type y el
  tamaño máximo; el archivo nunca atraviesa la capa de aplicación. `infraestructura/s3/comun.py`
  tiene la firma y el `head_object` que comparten los dos adaptadores.
- Autenticación: `Depends(usuario_actual)`. Con `COGNITO_USER_POOL_ID` y `COGNITO_CLIENT_ID`
  valida el access token de `Authorization: Bearer` contra las claves del user pool
  (`infraestructura/cognito/verificador.py`, detrás del puerto `VerificadorTokens`) y devuelve el
  `sub`; sin token o con uno inválido, `401 no_autenticado`. Sin esas variables (local, tests),
  todos son anónimos. El login entero está en `terraform/README.md` («Login con Cognito»).

## 5. Worker

Sin estado, sin base. Un proceso por instancia con `intra_op_num_threads = vCPU`.

```python
class ProveedorModelos(Protocol):
    def obtener(self, ref: RefModelo) -> ModeloCargado: ...   # contrato + sesión ONNX lista

class FuenteImagenes(Protocol):
    def leer(self, ref: RefObjeto) -> bytes: ...
```

- `ProveedorEfsS3`: busca `/mnt/modelos/<nombre>/<version>/`; si no está, baja de S3 a un
  directorio temporal y hace `rename` atómico (dos workers no se pisan). LRU de sesiones cargadas.
- `FuenteS3`: `get_object` con timeouts; `NoEncontrado` → 404.
- `Inferir.ejecutar`: `decodificar → preprocesar → motor.inferir → posprocesar`, todo `ateneo_ml`.
- Dependencias fijas por la AMI (`onnxruntime`, `numpy`, `pillow`, `pydicom`, `boto3`, `fastapi`,
  `uvicorn`, `psycopg`). Agregar una es reconstruir la imagen. `ateneo_ml` respeta esa lista.

## 6. Evaluador

Un bucle explícito. A `eval-1` **no se entra**, así que todo queda en el log y en la fila.

```python
def main():
    cfg = Settings(); cola, conjuntos, modelos, motor = armar(cfg)
    cola.reencolar_en_curso()                     # si eval-1 murió a mitad de una evaluación
    log.info("evaluador listo", instancia=cfg.instancia_id)
    while True:
        modelo = cola.tomar_pendiente()           # SKIP LOCKED + estado_evaluacion=en_curso
        if modelo is None:
            time.sleep(cfg.intervalo_segundos); continue
        EvaluarModelo(conjuntos, modelos, motor, cola, cfg).ejecutar(modelo)
```

`EvaluarModelo.ejecutar`:

1. Bajar `modelo.json` y `modelo.onnx` a un directorio temporal; construir `OnnxMotor`; validar
   que los tensores del contrato existen en el grafo con las formas declaradas.
2. `conjuntos.ultima_version(tipo_estudio)` (lista prefijos `vN/`), leer manifiesto y verdad,
   validar consistencia (specs §8). Si falla: `terminar_error`.
3. Por cada caso: `leer → decodificar → preprocesar → inferir → posprocesar`; acumular. Log cada
   25 casos. Un caso ilegible suma a `casos_con_error`.
4. `metricas.calcular(...)`; `terminar_ok(modelo, metricas, conjunto, version, manifiesto)`.
5. Borrar el temporal. Cualquier excepción no prevista → `terminar_error` y el bucle sigue.

```sql
-- tomar_pendiente
update modelo set estado_evaluacion='en_curso', evaluador_id=%(yo)s
 where id = (select id from modelo where estado_evaluacion='pendiente'
             order by publicado for update skip locked limit 1)
 returning *;
```

Identidad: el instance id leído de IMDSv2 (la NACL no lo filtra). Queda en la fila y en el log.

## 7. `ateneo_ml`: el contrato hecho código

```python
@dataclass(frozen=True)
class ContratoModelo:
    nombre: str; version: str; tipo_estudio: str; tarea: str
    entrada: EspecEntrada   # nombre, layout, forma, dtype, espacio_color, redimension, escala, media, desvio
    salida: EspecSalida     # nombre, tipo, etiquetas, positiva, umbral
    @staticmethod
    def desde_json(d: dict) -> "ContratoModelo": ...     # EntradaInvalida con el campo que falla

def preprocesar(img: PIL.Image.Image, e: EspecEntrada) -> np.ndarray:
    # 1. color: RGB | L | gris_replicado (convert("L").convert("RGB"), luma ITU-R 601, para modelos entrenados en gris)
    # 2. redimensión: estirar | recortar_centro, al alto×ancho de `forma`
    # 3. float32 / escala, luego (x - media) / desvio si están
    # 4. layout: HWC → NCHW si corresponde; agregar batch
class OnnxMotor(Motor): ...                              # InferenceSession, intra_op_num_threads
def posprocesar(salida, s: EspecSalida) -> Prediccion:   # logits→softmax | probabilidades | logit_sigmoide
def calcular_metricas(verdades, predicciones, probabilidades, etiquetas, positiva) -> dict
```

El backend necesita la misma validación de `modelo.json` sin traer `onnxruntime`: `contrato.py`
no importa nada pesado, así que el backend lo **copia** como `app/dominio/contrato.py` con un test
que compara ambos archivos byte a byte. Es la única duplicación consentida, y está vigilada.

Registros por diccionario (decodificadores por extensión, posprocesadores por `salida.tipo`,
métricas por `tarea`): agregar uno es agregar una entrada.

Tests sin modelo real: un ONNX diminuto generado en el test (una capa identidad) con tensores
fijos, más un test contra `modelo.onnx` real marcado `@slow` que solo corre si el archivo está.

## 8. Frontend

React + Vite + TypeScript, CSS propio, sin librerías.

Tres vistas, una por público: la **portada** cuenta qué es Ateneo y abre las otras dos;
**publicación** es la vista de quien sube modelos; **consulta** la de quien atiende pacientes. El
único estado que comparten es el que ya vive en la API.

```
src/
├── api/ cliente.ts · tipos.ts · modelos.ts · estudios.ts · inferencias.ts · trabajos.ts
│   └── s3.ts                   # subir un archivo con un presigned POST, con progreso (XHR)
├── hooks/
│   ├── useModelos.ts           # publicados + disponibles; refresco
│   ├── usePublicacion.ts       # subir el ONNX → publicar + polling del modelo cada 3 s
│   ├── useInferencia.ts        # crear estudio → POST a S3 → encolar → polling del trabajo cada 1,5 s
│   ├── useSalud.ts             # GET /api/health cada 10 s, para la barra y el pie
│   └── useTema.ts              # claro/oscuro; sin elección manda prefers-color-scheme
├── enrutador.tsx               # useRuta() + <Enlace>: History API, tres rutas, ~60 líneas
├── components/
│   ├── Marca · Navegacion · PieSitio · DiagramaFlujo        # identidad y marco del sitio
│   ├── SubirModelo · ListaDisponibles · CatalogoModelos · TarjetaEvaluacion
│   └── SelectorModelo · ResumenMedida · CargadorImagen · EstadoTrabajo · ResultadoInferencia · EstadoApi
├── pages/
│   ├── Inicio.tsx              # "/"          portada: qué es, el recorrido, las dos puertas
│   ├── Publicar.tsx            # "/publicar"  bucket → alta → evaluación en vivo → catálogo
│   └── Consulta.tsx            # "/consulta"  modelo medido → estudio → predicción
├── utilidades/ formato.ts · contrato.ts                     # lectura del modelo.json en el navegador
└── estilos/ base.css · sitio.css · paneles.css              # tokens, sitio, paneles
```

- Componentes sin `fetch`: reciben datos y callbacks. Los hooks usan `api/`. Cambiar la API es
  tocar `api/`.
- Polling con `setInterval` dentro del hook, cancelado al terminar o al desmontar. Cuando exista
  algo mejor (SSE), cambia el hook, no los componentes.
- Subida a S3 con el `presigned POST` tal cual (`FormData` con los campos + el archivo), en
  `api/s3.ts` y con `XMLHttpRequest`: es el único que informa el progreso, y un ONNX pesa decenas
  de MB. La usan las dos subidas, la del estudio y la del modelo.
- Rutas relativas (`/api/...`): en producción resuelven al ALB; en desarrollo, Vite hace proxy a
  `localhost:8080`. El código no distingue entornos, igual que el `index.html` de la guía.
- **Ruteo propio, no react-router.** `enrutador.tsx` es `useSyncExternalStore` sobre
  `history.pushState` más un `<Enlace>` que respeta ctrl/cmd/click del medio. Son tres rutas fijas
  y una dependencia menos que instalar en el despliegue; `sitio.py` ya devuelve `index.html` para
  cualquier ruta fuera de `/api`, así que recargar `/consulta` funciona. Si algún día hacen falta
  rutas con parámetros, entra react-router tocando solo este archivo.
- **Identidad visual**: la misma de los documentos del proyecto (verde clínico `#0E6B66`, Archivo
  para títulos, Source Sans 3 para el cuerpo, IBM Plex Mono para los datos), en tokens de CSS con
  tema claro y oscuro. Las fuentes vienen de Google Fonts con `display=swap` y una pila del sistema
  detrás: si el navegador no las alcanza, el sitio sigue legible.

## 9. Configuración por servicio

| Servicio | Variable | Uso |
|----------|----------|-----|
| backend | `DATABASE_URL` · `AWS_REGION` · `BUCKET_MODELOS` · `BUCKET_ESTUDIOS` · `INFERENCIA_URL` · `ORIGEN_WEB` | como en la guía |
| backend | `WEB_DIR=/opt/ateneo/web` · `TIMEOUT_INFERENCIA_S=30` · `MAX_INTENTOS=3` · `INTERVALO_DESPACHO_S=1` · `MAX_BYTES_ESTUDIO=20971520` | nuevos, con default |
| worker | `AWS_REGION` · `MODELOS_DIR=/mnt/modelos` · `BUCKET_MODELOS` (nuevo) · `CACHE_SESIONES=4` | caché EFS · LRU |
| evaluador | `AWS_REGION` · `BUCKET_EVALUACION` · `BUCKET_MODELOS` · `DATABASE_URL` · `INTERVALO_SEGUNDOS=10` · `DIRECTORIO_TRABAJO=/opt/worker/tmp` | bucle · temporales |
| todos (local) | `AWS_ENDPOINT_URL=http://localhost:9000` + credenciales de MinIO | boto3 lo lee solo; en AWS no se define |

`infra/*.env.example` documenta cada una sin secretos.

## 10. Desarrollo local

```
docker compose up -d                     # postgres:16 :5432 · minio :9000 (consola :9001) · crea los 4 buckets
python tools/migrar.py                   # aplica migraciones/ contra DATABASE_URL
python tools/descargar_modelo.py --solo-descargar   # deja modelo.onnx y modelo.json en ./tmp/modelo
                                                   # (para subirlos desde /publicar; sin la opción van a MinIO)
python tools/preparar_conjunto.py --hf hf-vision/chest-xray-pneumonia --por-clase 100 --salida ./tmp/torax-rx/v1
python tools/subir_conjunto.py ./tmp/torax-rx/v1
(cd backend  && uvicorn app.main:app --port 8080 --reload)
uvicorn worker.main:app --port 8081 --reload     # INFERENCIA_URL=http://localhost:8081 · MODELOS_DIR=./tmp/modelos
python -m evaluador.main
(cd frontend && npm run dev)                     # http://localhost:5173
```

- Los tres servicios Python corren en el host: así el `presigned POST` apunta a `localhost:9000` y
  el navegador lo alcanza. MinIO acepta CORS `*` por defecto.
- Los mismos scripts sirven contra AWS desde CloudShell: solo cambia `AWS_ENDPOINT_URL` (ausente).
- **Lo normal es correr todo con Docker** (`docker compose up -d --build`), que reproduce la topología: Postgres hace de RDS, MinIO de S3, y el DNS de Docker hace de ALB interno. Ver el README.

## 11. Pruebas

| Nivel | Qué | Con qué |
|-------|-----|---------|
| Dominio | `marcar_fallido` (3 intentos), `republicar` (409), `verificar_compatible`, validación de contrato | pytest, sin IO |
| Casos de uso | orquestación con fakes en memoria; despachador con un `ClienteInferencia` que falla N veces | pytest |
| `ateneo_ml` | preprocesamiento (NHWC/NCHW, gris replicado), posprocesamiento, métricas a mano; motor con ONNX de una capa | pytest + onnxruntime |
| Adaptadores | S3 contra `moto`; repositorios y `tomar_pendiente` concurrente contra Postgres en Docker | pytest + moto + docker |
| API | routers con casos de uso falsos (`dependency_overrides`); fallback a `index.html` | `TestClient` |
| Extremo a extremo | publicar + evaluar + inferir contra el compose local | a mano, con el README |
| Arquitectura | capas (`import-linter`); `contrato.py` idéntico en backend y `ateneo_ml` | CI |

## 12. Despliegue: qué zip lleva qué

| Artefacto | Contenido | Quién lo baja | Cómo se aplica |
|-----------|-----------|---------------|----------------|
| `backend/backend-latest.zip` | `backend/app/`, `backend/requirements.txt` | user data de `lt-app` | `refrescar.sh asg-app` |
| `worker/worker-latest.zip` | `worker/`, `evaluador/`, `ateneo_ml/` | user data de `lt-worker` y de `lt-eval` | `refrescar.sh asg-inf` · terminar y `run-instances` de `eval-1` |
| `config/*.env` | variables de §9 | user data de cada capa | mismo reemplazo |
| `s3://ateneo-web/` | build de Vite | user data de `lt-app` (`aws s3 sync` al arrancar) | `refrescar.sh asg-app` (sin CDN, las instancias tienen la copia) |
| `migraciones/*.sql` | esquema | `psql` desde una instancia app | antes del backend que lo necesita |

Orden del primer despliegue: migraciones → backend → worker → frontend (refresca app de nuevo) →
modelo a S3 → conjunto a S3 → lanzar `eval-1` → apretar **Publicar**.

## 13. Decisiones que este diseño deja abiertas a propósito

| Evolución | Qué cambia | Qué no cambia |
|-----------|------------|---------------|
| Cola SQS | `ColaTrabajos` y `ClienteInferencia` pasan a SQS; el worker consume en vez de escuchar | Casos de uso, dominio, `ateneo_ml`, tabla `trabajo` |
| El worker escribe el resultado (como sugiere la guía) | Un adaptador de `RepositorioTrabajos` en el worker con `insert … on conflict`; `DespacharTrabajo` deja de guardar | Todo lo demás |
| Historial de evaluaciones | Tabla `evaluacion` (modelo, conjunto, versión, métricas); la fila del modelo apunta a la vigente | API pública, UI |
| Juntas de varios modelos | `EncolarInferencia` crea N trabajos; un caso de uso `Consensuar` agrega | Worker, evaluador |
| DICOM | Un `DecodificadorImagen` más | Preprocesamiento, motor, métricas |
| Segmentación | Un posprocesador y un calculador de métricas por `tarea` | Motor, worker, evaluador |
| Roles (grupos de Cognito) | `usuario_actual` devuelve también los grupos del token; cada router pide el suyo | Casos de uso, login |
| CloudFront (cuando se pueda) | Sacar el `mount` del sitio; `ORIGEN_WEB` pasa a ser el dominio de CloudFront | API, despachador, todo lo demás |
