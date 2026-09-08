#!/bin/bash
# prender.sh — la rutina de al volver (guía §14). Tampoco lleva valores propios.
#
# OJO: no te vayas mientras corre. CloudShell cierra la sesión a los 20-30 minutos de
# inactividad y un proceso corriendo NO cuenta como actividad: el "wait" de la base puede
# tardar diez minutos en silencio y quedar cortado justo ahí.
#
# Se puede volver a correr sin miedo: si el NAT ya existe lo reutiliza en vez de crear otro.
set -euo pipefail
export AWS_PAGER=""

# --- Primero se averigua y se valida TODO. Recién después se crea algo que cueste plata:
# una Elastic IP asignada a la que después le falla el NAT queda colgada facturando.
VPC=$(aws ec2 describe-vpcs --filters Name=cidr,Values=10.0.0.0/16 --query 'Vpcs[0].VpcId' --output text)
[ "$VPC" != "None" ] || { echo "No encontré la VPC 10.0.0.0/16." >&2; exit 1; }

SUB_PUB=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=cidr-block,Values=10.0.0.0/24 \
          --query 'Subnets[0].SubnetId' --output text)
[ "$SUB_PUB" != "None" ] || { echo "No encontré la subred pública 10.0.0.0/24 en $VPC." >&2; exit 1; }
echo "vpc=$VPC  publica-a=$SUB_PUB"

# Las DOS subredes de aplicación, cada una con SU tabla: el asistente de VPC crea una tabla
# de ruteo por subred privada. Si le ponés la ruta a una sola, la mitad de las instancias
# nace sin internet y falla el dnf del user data.
RUTAS=""
for CIDR in 10.0.10.0/24 10.0.11.0/24; do
  SUB=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=cidr-block,Values=$CIDR \
        --query 'Subnets[0].SubnetId' --output text)
  [ "$SUB" != "None" ] || { echo "No encontré la subred $CIDR." >&2; exit 1; }
  RTB=$(aws ec2 describe-route-tables --filters Name=association.subnet-id,Values=$SUB \
        --query 'RouteTables[0].RouteTableId' --output text)
  [ "$RTB" != "None" ] || { echo "La subred $CIDR ($SUB) no tiene tabla de ruteo asociada." >&2; exit 1; }
  RUTAS="$RUTAS $RTB"
  echo "  $CIDR -> $SUB -> $RTB"
done

# --- Recién ahora, el NAT. Si ya hay uno vivo se reutiliza: crear un segundo es el error
# más caro que se puede cometer acá, y es fácil si el script se cortó a la mitad.
NAT=$(aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=$VPC Name=state,Values=available,pending \
      --query 'NatGateways[0].NatGatewayId' --output text)
if [ "$NAT" != "None" ]; then
  echo "ya había un NAT: $NAT (lo reutilizo)"
else
  EIP=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
  NAT=$(aws ec2 create-nat-gateway --subnet-id $SUB_PUB --allocation-id $EIP --query 'NatGateway.NatGatewayId' --output text)
  echo "NAT nuevo: $NAT (eip $EIP)"
fi
echo "esperando a que el NAT esté disponible…"
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT

for RTB in $RUTAS; do
  aws ec2 create-route --route-table-id $RTB --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT >/dev/null 2>&1 \
    || aws ec2 replace-route --route-table-id $RTB --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT
  echo "ruta puesta en $RTB"
done

# La base puede estar ya disponible si nunca la paraste o si este script se cortó antes.
ESTADO=$(aws rds describe-db-instances --db-instance-identifier ateneo-db --query 'DBInstances[0].DBInstanceStatus' --output text)
if [ "$ESTADO" = "stopped" ]; then
  aws rds start-db-instance --db-instance-identifier ateneo-db >/dev/null
  echo "base arrancando…"
else
  echo "base en '$ESTADO', no la toco"
fi
echo "esperando a que la base esté disponible (puede tardar diez minutos, sin imprimir nada)…"
aws rds wait db-instance-available --db-instance-identifier ateneo-db

aws autoscaling update-auto-scaling-group --auto-scaling-group-name asg-app --min-size 2 --desired-capacity 2
aws autoscaling update-auto-scaling-group --auto-scaling-group-name asg-inf --min-size 1 --desired-capacity 1
echo "asg-app en 2 · asg-inf en 1"

# eval-1 no se "prende": nace de la plantilla, y así vuelve a correr su autoprueba
aws ec2 run-instances --launch-template LaunchTemplateName=lt-eval,Version='$Latest' \
  --query 'Instances[0].InstanceId' --output text
