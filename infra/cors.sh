#!/bin/bash
# cors.sh — CORS de los dos buckets a los que el navegador sube archivos directo:
# el de estudios (la imagen del paciente) y el de modelos (el ONNX del publicador).
#
#   bash infra/cors.sh http://mi-alb-1234.us-east-1.elb.amazonaws.com
#
# Sin esto el navegador bloquea el POST prefirmado y la subida falla con un
# error de red que no dice por qué. Se corre una vez por bucket, o cada vez que
# cambia el DNS del balanceador.
set -euo pipefail
export AWS_PAGER=""
cd "$(dirname "$0")/.."
. infra/entorno.sh

ORIGEN="${1:?uso: cors.sh <origen>   p. ej. http://mi-alb-1234.us-east-1.elb.amazonaws.com}"
case "$ORIGEN" in
  http://*|https://*) ;;
  *) echo "El origen tiene que empezar con http:// o https:// (sin barra final)."; exit 1 ;;
esac
ORIGEN="${ORIGEN%/}"

REGLA=$(cat <<JSON
{"CORSRules":[{
  "AllowedOrigins": ["$ORIGEN"],
  "AllowedMethods": ["POST", "GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "ExposeHeaders": ["ETag"],
  "MaxAgeSeconds": 3000
}]}
JSON
)

for BUCKET in "$BUCKET_ESTUDIOS" "$BUCKET_MODELOS"; do
  aws s3api put-bucket-cors --bucket "$BUCKET" --cors-configuration "$REGLA"
  echo "CORS aplicado a $BUCKET para $ORIGEN"
done

echo "Comprobalo con: aws s3api get-bucket-cors --bucket $BUCKET_MODELOS"
