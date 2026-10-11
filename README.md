# Ateneo

Marketplace de modelos de IA clínica · Cloud Computing 82.08 · ITBA.

Pre-MVP: una portada que cuenta qué ofrece Ateneo y dos secciones detrás, una por público.
**Publicar un modelo** (el ONNX va del navegador directo al bucket con una URL prefirmada, la API
valida su contrato y `eval-1` lo mide contra el conjunto reservado) y **consultar un estudio**
(cola en Postgres, despachador en el backend, worker de inferencia detrás del ALB interno).

- [specs.md](specs.md) · qué hace: flujos, API, contrato del modelo, esquema, criterios de aceptación.
- [architecture.md](architecture.md) · cómo está construido: capas, puertos y adaptadores, SOLID, despliegue.
- [infra/DESPLIEGUE.md](infra/DESPLIEGUE.md) · en qué paso de la guía va cada pieza y qué dice cada `.env`.

## Estructura

```
ateneo_ml/    preprocesamiento + motor ONNX + métricas, compartido por worker y evaluador
backend/      FastAPI: API, sitio estático, despachador de trabajos (capa app)
worker/       FastAPI: /inferir (capa inferencia, sin estado, sin base)
evaluador/    proceso que evalúa modelos pendientes (eval-1, subred aislada)
frontend/     React + Vite + TypeScript (portada + publicación + consulta)
migraciones/  SQL
tools/        bajar y verificar el modelo, preparar y subir el conjunto, migrar
infra/        user data, .env de ejemplo, desplegar.sh, refrescar.sh
terraform/    toda la infraestructura como código, con SQS, SNS y Lambda
docker/       Dockerfiles para correr todo en local
```

## Correr en local (Docker)

Reproduce la topología de AWS: Postgres hace de RDS, MinIO de S3, y cada servicio corre en su
contenedor. El backend sirve el frontend compilado en `/`, igual que en la capa app.

```bash
docker compose up -d --build            # db, minio, migraciones, backend, worker, evaluador
```

**El sitio se compila adentro de la imagen del backend** (`docker/Dockerfile.backend` tiene una
etapa de node), así que después de tocar `frontend/` o `backend/` hay que reconstruir:
`docker compose up -d --build backend`. Si la interfaz es nueva pero el backend quedó viejo, subir
un modelo falla con «Method Not Allowed»: la ruta `POST /api/modelos/subidas` todavía no existe de
ese lado y el pedido cae en `GET /api/modelos/{id}`.

Abrí <http://localhost:8080>. Todavía no hay modelos ni conjunto reservado: los dos comandos de
acá abajo bajan el ONNX y el conjunto; el modelo se sube después desde la propia pantalla.

```bash
# 1. el modelo ONNX (16 MB) y su modelo.json → quedan en ./tmp/modelo, para subirlos desde la web
docker compose run --rm herramientas python tools/descargar_modelo.py --carpeta /salida/modelo --solo-descargar

# 2. el conjunto reservado (200 casos), bajado de Hugging Face: no hace falta cuenta de Kaggle
docker compose run --rm herramientas python tools/preparar_conjunto.py \n  --hf hf-vision/chest-xray-pneumonia --split test --por-clase 100 --salida /salida/torax-rx/v1
docker compose run --rm herramientas python tools/subir_conjunto.py /salida/torax-rx/v1
```

Después, en `/publicar`: arrastrá `tmp/modelo/modelo.onnx` y `tmp/modelo/modelo.json` a la zona de
subida y apretá **Subir y publicar** (el evaluador tarda 2-4 min en CPU con 200 casos). Y en
`/consulta`: **Consultar** con cualquiera de las radiografías que quedaron en
`tmp/torax-rx/v1/casos/`.

Útiles:

```bash
docker compose logs -f evaluador          # ver la evaluación avanzar
docker compose logs -f backend            # ver el despachador tomar trabajos
docker compose exec db psql -U ateneo -c "select nombre, estado_evaluacion, accuracy from modelo"
```

Consola de MinIO: <http://localhost:9001> (minioadmin / minioadmin).

## Desarrollo sin Docker (tests y frontend con recarga)

```bash
python -m venv .venv && .venv/Scripts/activate      # o source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                               # tests de ateneo_ml, evaluador, backend
cd frontend && npm install && npm run dev            # http://localhost:5173, proxy /api → :8080
```

El 5173 es **solo para desarrollar** con recarga en caliente, y necesita el Docker levantado: hace
proxy de `/api` al 8080. La aplicación se abre en <http://localhost:8080>, donde el backend sirve
el sitio y la API desde el mismo origen, igual que el ALB en AWS.

## Desplegar en AWS Academy

**Con Terraform (recomendado):** ver [terraform/README.md](terraform/README.md). En CloudShell:

```bash
git clone https://github.com/nnicokim/TP-AWS.git ~/ateneo && cd ~/ateneo   # después: git pull
bash terraform/scripts/bootstrap-estado.sh                 # una vez por cuenta
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
bash terraform/scripts/tf.sh apply -target='aws_s3_bucket.b'
bash terraform/scripts/entorno-desde-terraform.sh
bash infra/desplegar.sh todo
bash terraform/scripts/tf.sh apply                          # todo lo demás
bash terraform/scripts/tf.sh apply -var encendido=false     # antes de End Lab
```

Cada integrante que despliegue en su propio Learner Lab obtiene buckets con un sufijo al azar,
así que no hay choques de nombres (ver «Un equipo de varias personas» en el README de Terraform).

**A mano, como la guía:** ver [infra/DESPLIEGUE.md](infra/DESPLIEGUE.md). Resumen: `bash infra/desplegar.sh backend|worker|frontend`
sube los paquetes al bucket de despliegue y `bash infra/refrescar.sh asg-app|asg-inf` reemplaza las
instancias; `eval-1` se termina y se relanza desde `lt-eval`.
