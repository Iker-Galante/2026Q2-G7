# Ateneo

Marketplace de modelos de IA clínica · Cloud Computing 82.08 · ITBA.

Una portada que cuenta qué ofrece Ateneo y dos secciones detrás, una por público.
**Publicar un modelo** (el ONNX va del navegador directo al bucket con una URL prefirmada, la API
valida su contrato y el evaluador, en una subred aislada, lo mide contra el conjunto reservado) y
**consultar un estudio** (la API encola el pedido en SQS, un worker lo toma y el procesador escribe
el resultado).

Esta rama, `entrega3`, implementa la arquitectura de «Ateneo en AWS 2.0»: ECS Fargate, API Gateway
con HTTPS, Cognito, tres colas de SQS y un despliegue completo con `terraform apply`.

- [specs.md](specs.md) · qué hace: flujos, API, contrato del modelo, esquema, criterios de aceptación.
- [architecture.md](architecture.md) · cómo está construido: servicios, puertos y adaptadores, colas.
- [terraform/README.md](terraform/README.md) · la infraestructura, el login con Cognito y cómo desplegar.

## Estructura

```
ateneo_ml/    preprocesamiento + motor ONNX + métricas, compartido por worker y evaluador
backend/      imagen backend: la api (FastAPI) y el procesador (escribe los resultados)
worker/       imagen ml: lee la cola inferencias, sin base y sin puertos
evaluador/    imagen ml: lee la cola evaluaciones, en la subred aislada
frontend/     React + Vite + TypeScript (portada + publicación + consulta), con login de Cognito
migraciones/  SQL; las aplica el procesador al arrancar
tools/        bajar y verificar el modelo, preparar y subir el conjunto
terraform/    toda la infraestructura como código
docker/       Dockerfiles de las dos imágenes, de los tests y la configuración de ElasticMQ
```

## Correr en local (Docker)

Reproduce la topología de AWS: Postgres hace de RDS, MinIO de S3 y ElasticMQ de SQS (las mismas
tres colas, con sus colas de fallidos), y cada servicio corre en su contenedor. En local no hay
login: la api sirve el sitio en `/` y todos son anónimos.

```bash
docker compose up -d --build            # db, minio, sqs, migraciones, api, procesador, worker, evaluador
```

**El sitio se compila adentro de la imagen del backend** (`docker/Dockerfile.backend` tiene una
etapa de node), así que después de tocar `frontend/` o `backend/` hay que reconstruir:
`docker compose up -d --build api procesador`.

Abrí <http://localhost:8080>. Todavía no hay modelos ni conjunto reservado: los dos comandos de
acá abajo bajan el ONNX y el conjunto; el modelo se sube después desde la propia pantalla.

```bash
# 1. el modelo ONNX (16 MB) y su modelo.json → quedan en ./tmp/modelo, para subirlos desde la web
docker compose run --rm herramientas python tools/descargar_modelo.py --carpeta /salida/modelo --solo-descargar

# 2. el conjunto reservado (200 casos), bajado de Hugging Face: no hace falta cuenta de Kaggle
docker compose run --rm herramientas python tools/preparar_conjunto.py \
  --hf hf-vision/chest-xray-pneumonia --split test --por-clase 100 --salida /salida/torax-rx/v1
docker compose run --rm herramientas python tools/subir_conjunto.py /salida/torax-rx/v1
```

Después, en `/publicar`: arrastrá `tmp/modelo/modelo.onnx` y `tmp/modelo/modelo.json` a la zona de
subida y apretá **Subir y publicar** (el evaluador tarda 2-4 min en CPU con 200 casos). Y en
`/consulta`: **Consultar** con cualquiera de las radiografías que quedaron en
`tmp/torax-rx/v1/casos/`.

Útiles:

```bash
docker compose logs -f evaluador          # ver la evaluación avanzar
docker compose logs -f procesador         # ver llegar los resultados
docker compose exec db psql -U ateneo -c "select nombre, estado_evaluacion, accuracy from modelo"
```

Consola de MinIO: <http://localhost:9001> (minioadmin / minioadmin).

## Desarrollo sin Docker (tests y frontend con recarga)

```bash
python -m venv .venv && .venv/Scripts/activate      # o source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                               # tests de ateneo_ml, worker, evaluador, backend
cd frontend && npm install && npm run dev            # http://localhost:5173, proxy /api → :8080
```

En Windows sin el runtime de Visual C++, `onnx` no carga y sus tests se saltean:
`docker compose run --rm tests` corre la suite completa.

El 5173 es **solo para desarrollar** con recarga en caliente, y necesita el Docker levantado: hace
proxy de `/api` al 8080.

## Desplegar en AWS Academy

Ver [terraform/README.md](terraform/README.md). En CloudShell:

```bash
git clone https://github.com/nnicokim/TP-AWS.git ~/ateneo && cd ~/ateneo && git checkout entrega3
bash terraform/organization/scripts/bootstrap-estado.sh                 # una vez por cuenta
cp terraform/organization/terraform.tfvars.example terraform/organization/terraform.tfvars   # email_admin y email_alertas
bash terraform/organization/scripts/tf.sh apply                          # todo: red, base, imágenes, servicios
bash terraform/organization/scripts/tf.sh output url                     # el sitio
bash terraform/organization/scripts/tf.sh destroy                        # al terminar cada sesión de trabajo
```
