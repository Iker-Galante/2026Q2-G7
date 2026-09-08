#!/bin/bash
# generar-env.sh — escribe los tres .env y los sube a s3://$BUCKET_DEPLOY/config/.
#
#   bash infra/generar-env.sh
#
# Los nombres de bucket salen de infra/entorno.sh; el endpoint de la base y los DNS de los dos
# balanceadores los averigua solo; lo único que se tipea es la contraseña de la base. Así ningún
# nombre de bucket se escribe a mano dos veces, que es de donde salen la mitad de los errores.
#
# Es el paso 3 de la guía §15, y necesita que ya existan la base (§05) y los dos balanceadores
# (§7.4 y §8.4). Para la fase mockeada no sirve: ahí el backend.env tiene una sola línea.
set -euo pipefail
export AWS_PAGER=""
cd "$(dirname "$0")/.."

[ -f infra/entorno.sh ] || {
  echo "Falta infra/entorno.sh — es donde viven los nombres de tus buckets. Crealo con:" >&2
  echo "   cp infra/entorno.example.sh infra/entorno.sh   # y completá los cinco nombres" >&2
  exit 1
}
. infra/entorno.sh

REGION=${AWS_REGION:-$(aws configure get region 2>/dev/null || true)}
case "$REGION" in ""|None) REGION=us-east-1 ;; esac

RDS=$(aws rds describe-db-instances --db-instance-identifier ateneo-db \
      --query 'DBInstances[0].Endpoint.Address' --output text 2>/dev/null || true)
ALB=$(aws elbv2 describe-load-balancers --names alb-ateneo \
      --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || true)
ALB_INT=$(aws elbv2 describe-load-balancers --names alb-ateneo-int \
      --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || true)

printf 'base                 %s\n' "${RDS:-(no la encontré)}"
printf 'balanceador          %s\n' "${ALB:-(no lo encontré)}"
printf 'balanceador interno  %s\n' "${ALB_INT:-(no lo encontré)}"

for _p in "$RDS" "$ALB" "$ALB_INT"; do
  [ -n "$_p" ] && [ "$_p" != "None" ] || {
    echo "Falta alguna de las tres piezas de arriba. Creala antes de seguir (guía §05, §7.4, §8.4)." >&2
    exit 1
  }
done

read -rsp 'contraseña de la base: ' CLAVE || true; echo
[ -n "$CLAVE" ] || { echo "Sin contraseña no se puede armar la DATABASE_URL." >&2; exit 1; }

# Una contraseña con @, / o # parte la URL en dos y el error que se ve es «host desconocido».
CLAVE_URL=$(printf '%s' "$CLAVE" \
  | python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.stdin.read(),safe=""))' 2>/dev/null) || {
  echo "AVISO: no pude codificar la contraseña (¿falta python3?). Si tiene @, / o # la URL va a salir rota." >&2
  CLAVE_URL=$CLAVE
}
unset CLAVE

URL="postgresql://ateneo:$CLAVE_URL@$RDS:5432/ateneo"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/backend.env" <<FIN
DATABASE_URL=$URL
AWS_REGION=$REGION
BUCKET_MODELOS=$BUCKET_MODELOS
BUCKET_ESTUDIOS=$BUCKET_ESTUDIOS
INFERENCIA_URL=http://$ALB_INT:8081
ORIGEN_WEB=http://$ALB
FIN

cat > "$TMP/worker.env" <<FIN
AWS_REGION=$REGION
MODELOS_DIR=/mnt/modelos
FIN

cat > "$TMP/evaluador.env" <<FIN
AWS_REGION=$REGION
BUCKET_EVALUACION=$BUCKET_EVALUACION
BUCKET_MODELOS=$BUCKET_MODELOS
DATABASE_URL=$URL
FIN

SUBIDOS=""
for _f in backend worker evaluador; do
  aws s3 cp "$TMP/$_f.env" "s3://$BUCKET_DEPLOY/config/$_f.env" \
    || { echo "FALLÓ al subir $_f.env. Subidos hasta acá:$SUBIDOS" >&2; exit 1; }
  SUBIDOS="$SUBIDOS $_f"
done
unset CLAVE_URL URL

echo
echo "Los tres subidos. Verificá:  aws s3 ls s3://$BUCKET_DEPLOY/config/"
echo "Se aplican reemplazando instancias:"
echo "   bash infra/refrescar.sh asg-app"
echo "   bash infra/refrescar.sh asg-inf"
echo "   y eval-1: terminarla y volver a lanzarla desde lt-eval"
