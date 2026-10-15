"""Disparador de post-confirmación de Cognito: pone a quien se registró solo en su grupo.

Instituciones y publicadores se registran por clientes distintos (cognito.tf); el evento trae el
cliente con el que se confirmó la cuenta, y su nombre dice el grupo. Corre solo al confirmar un
registro, no al recuperar una contraseña.

Si algo falla, el usuario igual queda confirmado (un error acá le rompería el registro): queda
sin grupo, y el log lo dice.
"""

from __future__ import annotations

import json
import logging
import os

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

cognito = boto3.client("cognito-idp")
GRUPO_POR_CLIENTE = json.loads(os.environ["GRUPO_POR_CLIENTE"])   # {"ateneo-institucion": "admin_institucion", …}
GRUPO_POR_DEFECTO = os.environ.get("GRUPO_POR_DEFECTO", "publicador")


def handler(evento: dict, _contexto) -> dict:
    if evento.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return evento

    pool = evento["userPoolId"]
    usuario = evento["userName"]
    cliente_id = (evento.get("callerContext") or {}).get("clientId")
    try:
        grupo = GRUPO_POR_DEFECTO
        if cliente_id:
            nombre = cognito.describe_user_pool_client(UserPoolId=pool, ClientId=cliente_id)["UserPoolClient"]["ClientName"]
            grupo = GRUPO_POR_CLIENTE.get(nombre, GRUPO_POR_DEFECTO)
        cognito.admin_add_user_to_group(UserPoolId=pool, Username=usuario, GroupName=grupo)
        log.info("usuario %s al grupo %s", usuario, grupo)
    except Exception:                                              # noqa: BLE001
        log.exception("no se pudo asignar el grupo a %s", usuario)
    return evento
