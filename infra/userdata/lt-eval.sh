#!/bin/bash
# User data de lt-eval, versión "Después · el evaluador de verdad" (guía §9.5).
# Arriba la autoprueba de aislamiento de §9.2 (sin set -e: la 1 TIENE que fallar);
# abajo el arranque del evaluador. Reemplazá el endpoint de RDS en la comprobación 5.

echo "=== AISLAMIENTO 1 · ¿sale a internet? (tiene que fallar) ==="
if curl -sS -m 5 https://www.google.com -o /dev/null; then echo "RESULTADO 1: LLEGA A INTERNET · MAL"; else echo "RESULTADO 1: sin salida a internet · OK"; fi

echo "=== AISLAMIENTO 2 · ¿llega a S3 por el endpoint de la VPC? ==="
if aws s3api list-objects-v2 --bucket ateneo-evaluacion-g7 --max-keys 1 >/dev/null; then echo "RESULTADO 2: S3 accesible por el endpoint · OK"; else echo "RESULTADO 2: no llega a S3 o el bucket no existe · MAL"; fi

echo "=== AISLAMIENTO 3 · ¿está el conjunto en su prefijo? ==="
if aws s3 ls s3://ateneo-evaluacion-g7/torax-rx/v1/ --recursive | head -3; then echo "RESULTADO 3: el conjunto está en su lugar · OK"; else echo "RESULTADO 3: el prefijo está vacío · MAL"; fi

echo "=== AISLAMIENTO 4 · ¿puede leer un caso desde adentro? ==="
if aws s3 cp s3://ateneo-evaluacion-g7/torax-rx/v1/manifiesto.json /tmp/ >/dev/null; then echo "RESULTADO 4: lectura desde la VPC · OK"; else echo "RESULTADO 4: no pudo leer · MAL"; fi

echo "=== AISLAMIENTO 5 · ¿llega a la base? ==="
if timeout 5 bash -c "</dev/tcp/ateneo-db.abc123.us-east-1.rds.amazonaws.com/5432"; then echo "RESULTADO 5: la base responde · OK"; else echo "RESULTADO 5: no llega a la base · MAL"; fi

echo "=== FIN DE LA AUTOPRUEBA ==="

set -euxo pipefail
aws s3 cp s3://ateneo-deploy-g7/worker/worker-latest.zip /opt/worker/
cd /opt/worker
unzip -o worker-latest.zip
aws s3 cp s3://ateneo-deploy-g7/config/evaluador.env /etc/ateneo.env
chmod 600 /etc/ateneo.env
mkdir -p /opt/worker/tmp

systemctl reset-failed ateneo-evaluador
systemctl start ateneo-evaluador
