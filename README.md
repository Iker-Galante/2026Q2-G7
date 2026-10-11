# Ateneo

Marketplace de modelos de IA clínica · Cloud Computing 82.08 · ITBA.

Pre-MVP: una pantalla para **publicar un modelo** (simulado: el ONNX ya está en S3, el botón lo da
de alta y `eval-1` lo evalúa contra el conjunto reservado) e **inferir una imagen** (cola en
Postgres, despachador en el backend, worker de inferencia detrás del ALB interno).

- [specs.md](specs.md) · qué hace: flujos, API, contrato del modelo, esquema, criterios de aceptación.
- [architecture.md](architecture.md) · cómo está construido: capas, puertos y adaptadores, SOLID, despliegue.
- [infra/DESPLIEGUE.md](infra/DESPLIEGUE.md) · en qué paso de la guía va cada pieza y qué dice cada `.env`.

## Estructura

```
ateneo_ml/    preprocesamiento + motor ONNX + métricas, compartido por worker y evaluador
backend/      FastAPI: API, sitio estático, despachador de trabajos (capa app)
worker/       FastAPI: /inferir (capa inferencia, sin estado, sin base)
evaluador/    proceso que evalúa modelos pendientes (eval-1, subred aislada)
frontend/     React + Vite + TypeScript (una página: Laboratorio)
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

Abrí <http://localhost:8080>. Todavía no hay modelos: hay que "subir uno a mano".

```bash
# 1. el modelo ONNX (16 MB) → queda en ./tmp/modelo y en el bucket ateneo-modelos de MinIO
docker compose run --rm herramientas python tools/descargar_modelo.py --carpeta /salida/modelo

# 2. el conjunto reservado (200 casos), bajado de Hugging Face: no hace falta cuenta de Kaggle
docker compose run --rm herramientas python tools/preparar_conjunto.py \n  --hf hf-vision/chest-xray-pneumonia --split test --por-clase 100 --salida /salida/torax-rx/v1
docker compose run --rm herramientas python tools/subir_conjunto.py /salida/torax-rx/v1
```

Después, en la pantalla: **Publicar modelo** (el evaluador tarda 2-4 min en CPU con 200 casos)
e **Inferir** con cualquiera de las radiografías que quedaron en `tmp/torax-rx/v1/casos/`.

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
