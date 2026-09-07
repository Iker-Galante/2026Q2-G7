#!/bin/bash
# refrescar.sh — reemplaza las instancias de un grupo (el lab no permite instance refresh). Guía §11.
set -euo pipefail
export AWS_PAGER=""
GRUPO="${1:?uso: refrescar.sh <nombre-del-asg>}"

IDS=$(aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names "$GRUPO" \
      --query 'AutoScalingGroups[0].Instances[].InstanceId' --output text)
[ -z "$IDS" ] && { echo "El grupo $GRUPO no tiene instancias."; exit 0; }

echo "Terminando: $IDS"
aws ec2 terminate-instances --instance-ids $IDS >/dev/null
echo "El grupo lanza reemplazos en un par de minutos: Auto Scaling Groups → $GRUPO → Activity"
