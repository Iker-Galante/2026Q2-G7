#!/bin/bash
# bootstrap-estado.sh — crea, una sola vez, el bucket donde Terraform guarda su estado.
#
#   bash terraform/organization/scripts/bootstrap-estado.sh
#
# El estado tiene la contraseña de la base y los ids de todo lo creado: va en un bucket
# privado, cifrado y versionado, separado de los cinco de la aplicación (que Terraform sí
# administra y podría borrar). Lo bloquea un archivo .tflock en el mismo bucket (use_lockfile).
# Escribe terraform/organization/backend.hcl, que lee "terraform init -backend-config=backend.hcl".
set -euo pipefail
export AWS_PAGER=""
cd "$(dirname "$0")/.."

REGION=${AWS_REGION:-us-east-1}
CUENTA=$(aws sts get-caller-identity --query Account --output text)
BUCKET="ateneo-tfstate-$CUENTA"

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "ya existe $BUCKET (lo reutilizo)"
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  echo "creado $BUCKET"
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled

cat > backend.hcl <<FIN
bucket       = "$BUCKET"
key          = "ateneo/terraform.tfstate"
region       = "$REGION"
encrypt      = true
use_lockfile = true
FIN
echo "escrito terraform/organization/backend.hcl"
