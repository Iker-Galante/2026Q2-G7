#!/bin/bash
# buckets.sh — crea y borra los buckets de la aplicación con el CLI, porque el provider no puede.
#
#   bash terraform/organization/scripts/buckets.sh crear  ateneo-modelos-abc123
#   bash terraform/organization/scripts/buckets.sh borrar ateneo-modelos-abc123
#
# Lo llama Terraform (s3.tf, terraform_data.buckets); no hace falta correrlo a mano.
#
# Por qué existe. El Learner Lab tiene un deny explícito sobre s3:GetBucketObjectLockConfiguration
# en una SCP de la organización, y el provider de AWS lee esa configuración cada vez que refresca
# un `aws_s3_bucket`, incluso cuando el bucket no usa object lock. El resultado es un AccessDenied
# fatal en cada apply:
#
#   Error: reading S3 Bucket (ateneo-web-xxxxxx) object lock configuration: ... AccessDenied:
#   ... with an explicit deny in a service control policy
#
# No se arregla dando permisos —una SCP no se sobreescribe desde la cuenta— ni pineando el
# provider: la lectura está en el read del recurso desde hace años y el AccessDenied no está en
# la lista de errores que tolera. El CLI sí puede crear y borrar buckets, así que la creación sale
# del provider y Terraform sigue administrando todo lo demás (políticas, cifrado, versionado,
# ciclo de vida, CORS, sitio), que son recursos aparte y cada uno lee solo lo suyo.
set -euo pipefail
export AWS_PAGER=""

ACCION=${1:?uso: buckets.sh crear|borrar <nombre>}
BUCKET=${2:?uso: buckets.sh crear|borrar <nombre>}
REGION=${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}

existe() { aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; }

crear() {
  if existe; then
    echo "$BUCKET ya existe, lo reutilizo"
  else
    # us-east-1 es la única región que no lleva --create-bucket-configuration.
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
    echo "creado $BUCKET"
  fi
  # Las etiquetas las ponía el provider con el recurso; acá van a mano.
  aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging \
    "TagSet=[{Key=Name,Value=$BUCKET},{Key=Proyecto,Value=ateneo},{Key=Gestion,Value=terraform}]"
}

# Un bucket no se borra con objetos adentro, y en los versionados `rm` deja las versiones viejas
# y los marcadores de borrado: hay que barrer las dos cosas antes del rb.
purgar() {
  aws s3 rm "s3://$BUCKET" --recursive --only-show-errors || true
  while :; do
    local cuantas
    cuantas=$(aws s3api list-object-versions --bucket "$BUCKET" --max-keys 500 \
      --query 'length([Versions, DeleteMarkers][][])' --output text 2>/dev/null || echo 0)
    case "$cuantas" in 0 | None | "") break ;; esac
    local lote
    lote=$(aws s3api list-object-versions --bucket "$BUCKET" --max-keys 500 \
      --query '{Objects: [Versions, DeleteMarkers][][].{Key: Key, VersionId: VersionId}}' \
      --output json)
    aws s3api delete-objects --bucket "$BUCKET" --delete "$lote" >/dev/null
  done
}

borrar() {
  if ! existe; then
    echo "$BUCKET no está, nada que borrar"
    return 0
  fi
  purgar
  if aws s3api delete-bucket --bucket "$BUCKET" 2>/dev/null; then
    echo "borrado $BUCKET"
  else
    # El destroy sigue igual (on_failure = continue): un bucket que sobrevive cuesta centavos y
    # el próximo apply lo reutiliza. Pero conviene saber que quedó.
    echo "AVISO: no se pudo borrar $BUCKET. Borralo a mano: aws s3 rb s3://$BUCKET --force" >&2
    return 1
  fi
}

case "$ACCION" in
  crear) crear ;;
  borrar) borrar ;;
  *) echo "acción desconocida: $ACCION (crear|borrar)" >&2; exit 2 ;;
esac
