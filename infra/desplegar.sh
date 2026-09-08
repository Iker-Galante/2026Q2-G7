#!/bin/bash
# desplegar.sh — arma los zips y el build y los sube a TU bucket de despliegue.
# Los nombres de los buckets salen de infra/entorno.sh (guía §04); acá no hay ninguno escrito.
# Se corre en la terminal del navegador, desde cualquier carpeta.
#
#   bash infra/desplegar.sh backend    → backend-latest.zip   · después: refrescar.sh asg-app
#   bash infra/desplegar.sh worker     → worker-latest.zip    · después: refrescar.sh asg-inf  (y relanzar eval-1)
#   bash infra/desplegar.sh frontend   → build al bucket web  · después: refrescar.sh asg-app
#   bash infra/desplegar.sh todo
set -euo pipefail
export AWS_PAGER=""
cd "$(dirname "$0")/.."

[ -f infra/entorno.sh ] || {
  echo "Falta infra/entorno.sh — es donde viven los nombres de tus buckets. Crealo con:" >&2
  echo "   cp infra/entorno.example.sh infra/entorno.sh   # y completá los cinco nombres" >&2
  exit 1
}
. infra/entorno.sh

QUE="${1:?uso: desplegar.sh backend|worker|frontend|todo}"

backend() {
  rm -f /tmp/backend-latest.zip
  zip -qr /tmp/backend-latest.zip backend/ -x "*/__pycache__/*" "*.pyc" "backend/tests/*"
  aws s3 cp /tmp/backend-latest.zip "s3://$BUCKET_DEPLOY/backend/backend-latest.zip"
  rm /tmp/backend-latest.zip
  echo "backend subido · ahora: bash infra/refrescar.sh asg-app"
}

worker() {
  rm -f /tmp/worker-latest.zip
  # ateneo_ml va en el mismo zip: worker y evaluador lo importan como paquete hermano (architecture.md §2)
  zip -qr /tmp/worker-latest.zip worker/ evaluador/ ateneo_ml/ -x "*/__pycache__/*" "*.pyc"
  aws s3 cp /tmp/worker-latest.zip "s3://$BUCKET_DEPLOY/worker/worker-latest.zip"
  rm /tmp/worker-latest.zip
  echo "worker subido · ahora: bash infra/refrescar.sh asg-inf  · y terminar + run-instances de eval-1"
}

frontend() {
  (cd frontend && { npm ci || npm install; } && npm run build)
  aws s3 sync frontend/dist/ "s3://$BUCKET_WEB/" --delete
  rm -rf frontend/node_modules          # el giga de CloudShell
  echo "frontend subido · ahora: bash infra/refrescar.sh asg-app"
}

case "$QUE" in
  backend)  backend ;;
  worker)   worker ;;
  frontend) frontend ;;
  todo)     backend; worker; frontend ;;
  *) echo "uso: desplegar.sh backend|worker|frontend|todo"; exit 2 ;;
esac
