#!/bin/bash
# entorno-desde-terraform.sh — escribe infra/entorno.sh con los buckets que creó Terraform.
#
#   bash terraform/scripts/entorno-desde-terraform.sh
#
# Así infra/desplegar.sh y infra/refrescar.sh siguen funcionando igual que con la guía:
# los cinco nombres ya no se eligen a mano, salen del estado.
set -euo pipefail
DIR=$(cd "$(dirname "$0")/.." && pwd)
B=$(bash "$DIR/scripts/tf.sh" output -json buckets)
val() { printf '%s' "$B" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }

cat > "$DIR/../infra/entorno.sh" <<FIN
# Generado por terraform/scripts/entorno-desde-terraform.sh — no editar a mano.
BUCKET_DEPLOY="$(val deploy)"
BUCKET_WEB="$(val web)"
BUCKET_MODELOS="$(val modelos)"
BUCKET_ESTUDIOS="$(val estudios)"
BUCKET_EVALUACION="$(val evaluacion)"
FIN
echo "escrito infra/entorno.sh"
cat "$DIR/../infra/entorno.sh"
