#!/bin/bash
# User data de lt-eval, versión "Después · el evaluador de verdad" (guía §9.5).
# Arriba la autoprueba de aislamiento de §9.2 (sin set -e: la 1 TIENE que fallar);
# abajo el arranque del evaluador. Los huecos los llena "bash infra/userdata.sh lt-eval",
# que lee los buckets de infra/entorno.sh y averigua el endpoint de RDS solo.

echo "=== AISLAMIENTO 1 · ¿sale a internet? (tiene que fallar) ==="
if curl -sS -m 5 https://www.google.com -o /dev/null; then echo "RESULTADO 1: LLEGA A INTERNET · MAL"; else echo "RESULTADO 1: sin salida a internet · OK"; fi

echo "=== AISLAMIENTO 2 · ¿llega a S3 por el endpoint de la VPC? ==="
if aws s3api list-objects-v2 --bucket __BUCKET_EVALUACION__ --max-keys 1 >/dev/null; then echo "RESULTADO 2: S3 accesible por el endpoint · OK"; else echo "RESULTADO 2: no llega a S3 o el bucket no existe · MAL"; fi

echo "=== AISLAMIENTO 3 · ¿está el conjunto en su prefijo? ==="
# Sin pipe a head: el "if" mira el codigo del ultimo comando del pipe, y head sale 0 aunque
# no le entre nada, asi que la comprobacion daria OK siempre. Se guarda y se mira si vino vacio.
LISTADO=$(aws s3 ls s3://__BUCKET_EVALUACION__/torax-rx/v1/ --recursive 2>&1)
if [ -n "$LISTADO" ]; then echo "$LISTADO" | head -3; echo "RESULTADO 3: el conjunto está en su lugar · OK"; else echo "RESULTADO 3: el prefijo está vacío o no se pudo listar · MAL"; fi

echo "=== AISLAMIENTO 4 · ¿puede leer un caso desde adentro? ==="
if aws s3 cp s3://__BUCKET_EVALUACION__/torax-rx/v1/manifiesto.json /tmp/ >/dev/null; then echo "RESULTADO 4: lectura desde la VPC · OK"; else echo "RESULTADO 4: no pudo leer · MAL"; fi

echo "=== AISLAMIENTO 5 · ¿llega a la base? ==="
if timeout 5 bash -c "</dev/tcp/__ENDPOINT_RDS__/5432"; then echo "RESULTADO 5: la base responde · OK"; else echo "RESULTADO 5: no llega a la base · MAL"; fi

echo "=== FIN DE LA AUTOPRUEBA ==="

set -euxo pipefail
aws s3 cp s3://__BUCKET_DEPLOY__/worker/worker-latest.zip /opt/worker/
cd /opt/worker
unzip -o worker-latest.zip
aws s3 cp s3://__BUCKET_DEPLOY__/config/evaluador.env /etc/ateneo.env
chmod 600 /etc/ateneo.env
mkdir -p /opt/worker/tmp

systemctl reset-failed ateneo-evaluador || true
systemctl start ateneo-evaluador
