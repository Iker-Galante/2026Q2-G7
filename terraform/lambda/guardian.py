"""Guardián del presupuesto: apaga lo que haya quedado prendido (guía §14).

Corre todas las noches desde EventBridge. Hace lo mismo que la rutina de antes de End Lab,
para el día que alguien se olvida: grupos en 0, eval-1 terminada, RDS detenida, NAT borrado
y su IP liberada. Al terminar manda un resumen al tema de SNS si hizo algo.

No toca nada que Terraform no recree: el próximo `terraform apply` (con encendido = true)
vuelve a dejar todo como está declarado.
"""

from __future__ import annotations

import os
import time

import boto3

ec2 = boto3.client("ec2")
asg = boto3.client("autoscaling")
rds = boto3.client("rds")
sns = boto3.client("sns")


def _grupos(acciones: list[str]) -> None:
    for nombre in os.environ["GRUPOS"].split(","):
        r = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[nombre])["AutoScalingGroups"]
        if r and (r[0]["DesiredCapacity"] > 0 or r[0]["MinSize"] > 0):
            asg.update_auto_scaling_group(AutoScalingGroupName=nombre, MinSize=0, MaxSize=0, DesiredCapacity=0)
            acciones.append(f"{nombre} en 0 (tenía {r[0]['DesiredCapacity']})")


def _evaluador(acciones: list[str]) -> None:
    r = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": ["eval-1"]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
    ])
    ids = [i["InstanceId"] for res in r["Reservations"] for i in res["Instances"]]
    if ids:
        ec2.terminate_instances(InstanceIds=ids)
        acciones.append(f"eval-1 terminada: {', '.join(ids)}")


def _base(acciones: list[str]) -> None:
    ident = os.environ["RDS_ID"]
    try:
        estado = rds.describe_db_instances(DBInstanceIdentifier=ident)["DBInstances"][0]["DBInstanceStatus"]
    except rds.exceptions.DBInstanceNotFoundFault:
        return
    if estado == "available":
        rds.stop_db_instance(DBInstanceIdentifier=ident)
        acciones.append(f"{ident} deteniéndose")
    elif estado not in ("stopped", "stopping"):
        acciones.append(f"{ident} en '{estado}': no se pudo detener, mirala")


def _nat(acciones: list[str], contexto) -> None:
    if os.environ.get("BORRAR_NAT", "true") != "true":
        return
    nats = ec2.describe_nat_gateways(Filters=[
        {"Name": "vpc-id", "Values": [os.environ["VPC_ID"]]},
        {"Name": "state", "Values": ["available", "pending"]},
    ])["NatGateways"]
    for nat in nats:
        ec2.delete_nat_gateway(NatGatewayId=nat["NatGatewayId"])
        acciones.append(f"NAT {nat['NatGatewayId']} borrándose")
        ips = [a["AllocationId"] for a in nat.get("NatGatewayAddresses", []) if a.get("AllocationId")]
        # La IP se libera recién cuando el NAT terminó de borrarse.
        while contexto.get_remaining_time_in_millis() > 20_000:
            estado = ec2.describe_nat_gateways(NatGatewayIds=[nat["NatGatewayId"]])["NatGateways"][0]["State"]
            if estado == "deleted":
                break
            time.sleep(10)
        for ip in ips:
            try:
                ec2.release_address(AllocationId=ip)
                acciones.append(f"Elastic IP {ip} liberada")
            except Exception as e:  # noqa: BLE001 — se informa y se sigue
                acciones.append(f"no pude liberar {ip}: {e}")


def handler(evento, contexto):
    acciones: list[str] = []
    for paso in (_grupos, _evaluador, _base):
        try:
            paso(acciones)
        except Exception as e:  # noqa: BLE001 — una rutina de apagado no aborta a la mitad
            acciones.append(f"falló {paso.__name__}: {e}")
    try:
        _nat(acciones, contexto)
    except Exception as e:  # noqa: BLE001
        acciones.append(f"falló _nat: {e}")

    print({"acciones": acciones})
    if acciones and os.environ.get("TEMA_SNS"):
        sns.publish(
            TopicArn=os.environ["TEMA_SNS"],
            Subject="Ateneo: el guardián apagó recursos",
            Message="Quedaron cosas prendidas y las apagué:\n\n- " + "\n- ".join(acciones)
                    + "\n\nPara volver a prender todo: terraform apply (con encendido = true).",
        )
    return {"acciones": acciones}
