#!/bin/bash
# apagar.sh — la rutina de antes de cada End Lab (guía §14).
# No lleva ningún valor propio: averigua la VPC y el NAT a partir del CIDR 10.0.0.0/16,
# así que funciona igual en cualquier cuenta y en cualquier reconstrucción del laboratorio.
#
# Ningún paso aborta a los siguientes: una rutina de apagado que se corta a la mitad
# es peor que una que informa lo que no pudo hacer y sigue.
set -uo pipefail
export AWS_PAGER=""
PROBLEMAS=0
aviso() { echo "  ! $*" >&2; PROBLEMAS=$((PROBLEMAS + 1)); }

VPC=$(aws ec2 describe-vpcs --filters Name=cidr,Values=10.0.0.0/16 --query 'Vpcs[0].VpcId' --output text 2>/dev/null || true)
if [ -z "$VPC" ] || [ "$VPC" = "None" ]; then
  echo "No encontré una VPC con CIDR 10.0.0.0/16. Sin eso no puedo tocar el NAT," >&2
  echo "que es lo más caro que queda prendido. Revisá que la sesión del lab esté abierta." >&2
  exit 1
fi
echo "vpc=$VPC"

for G in asg-app asg-inf; do
  aws autoscaling update-auto-scaling-group --auto-scaling-group-name "$G" --min-size 0 --desired-capacity 0 \
    && echo "$G en 0" || aviso "no pude bajar $G (¿existe con ese nombre?)"
done

# pending y stopping también: una instancia recién lanzada no está "running" todavía
EVAL=$(aws ec2 describe-instances \
       --filters Name=tag:Name,Values=eval-1 Name=instance-state-name,Values=pending,running,stopping,stopped \
       --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null || true)
if [ -n "$EVAL" ]; then
  aws ec2 terminate-instances --instance-ids $EVAL >/dev/null && echo "eval-1 terminada: $EVAL" || aviso "no pude terminar eval-1"
else
  echo "eval-1: no hay ninguna"
fi

ESTADO=$(aws rds describe-db-instances --db-instance-identifier ateneo-db \
         --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || true)
case "$ESTADO" in
  available) aws rds stop-db-instance --db-instance-identifier ateneo-db >/dev/null \
               && echo "base deteniéndose" || aviso "la base está available pero no la pude detener" ;;
  stopped|stopping) echo "base ya detenida ($ESTADO)" ;;
  "")        aviso "no pude consultar la base (¿venció la sesión del lab?)" ;;
  *)         aviso "la base está en '$ESTADO' y no se puede detener así — volvé a mirarla en un rato" ;;
esac

NAT=$(aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=$VPC Name=state,Values=available,pending \
      --query 'NatGateways[0].NatGatewayId' --output text 2>/dev/null || true)
if [ -n "$NAT" ] && [ "$NAT" != "None" ]; then
  aws ec2 delete-nat-gateway --nat-gateway-id $NAT >/dev/null && echo "NAT $NAT borrándose"
  echo "esperando a que el NAT se borre para poder liberar la IP (hasta 5 minutos)…"
  INTENTOS=0
  until [ "$(aws ec2 describe-nat-gateways --nat-gateway-ids $NAT --query 'NatGateways[0].State' --output text 2>/dev/null)" = "deleted" ]; do
    INTENTOS=$((INTENTOS + 1))
    if [ $INTENTOS -gt 20 ]; then aviso "el NAT sigue sin borrarse; volvé a correr este script en un rato"; break; fi
    printf '.'; sleep 15
  done
  echo
else
  echo "NAT: no hay ninguno activo en esta VPC"
fi

# Barrido final: cualquier Elastic IP sin asociar cuesta plata. Cubre el caso de una
# corrida anterior que se cortó justo entre borrar el NAT y liberar su dirección.
SUELTAS=$(aws ec2 describe-addresses --query 'Addresses[?AssociationId==`null`].AllocationId' --output text 2>/dev/null || true)
for A in $SUELTAS; do
  aws ec2 release-address --allocation-id "$A" >/dev/null && echo "Elastic IP liberada: $A" || aviso "no pude liberar $A"
done
[ -z "$SUELTAS" ] && echo "Elastic IPs sueltas: ninguna"

echo
echo "--- instancias que siguen corriendo ---"
echo "(las que están terminándose pueden tardar un minuto más en desaparecer de esta lista)"
aws ec2 describe-instances --filters Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text

if [ $PROBLEMAS -gt 0 ]; then
  echo; echo "TERMINÓ CON $PROBLEMAS AVISO(S) — miralos antes de hacer End Lab." >&2
  exit 1
fi
echo; echo "Todo apagado. Ahora sí, End Lab."
