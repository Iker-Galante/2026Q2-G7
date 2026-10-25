"""El verificador de access tokens de Cognito, con una clave RSA propia en lugar del JWKS del pool."""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.dominio.errores import NoAutenticado, ServicioNoDisponible
from app.infraestructura.cognito.verificador import VerificadorCognito

POOL = "us-east-1_prueba"
CLIENTE = "cliente123"
EMISOR = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL}"

CLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTRA_CLAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class JwksFijo:
    """Hace de PyJWKClient: siempre la clave pública de CLAVE."""
    def __init__(self, error: Exception | None = None):
        self.error = error

    def get_signing_key_from_jwt(self, _token):
        if self.error:
            raise self.error
        return SimpleNamespace(key=CLAVE.public_key())


def _token(clave=CLAVE, **cambios) -> str:
    claims = {"sub": "sub-123", "iss": EMISOR, "client_id": CLIENTE, "token_use": "access",
              "exp": int(time.time()) + 300, "scope": "openid email"}
    claims.update(cambios)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, clave, algorithm="RS256")


@pytest.fixture
def verificador():
    return VerificadorCognito("us-east-1", POOL, [CLIENTE, "cliente-institucion"], jwks=JwksFijo())


def test_access_token_valido_devuelve_el_usuario_con_sus_grupos(verificador):
    u = verificador.verificar(_token(**{"cognito:groups": ["publicador"]}))
    assert u.sub == "sub-123" and u.grupos == ("publicador",)


def test_acepta_cualquiera_de_los_clientes_del_pool(verificador):
    assert verificador.verificar(_token(client_id="cliente-institucion")).grupos == ()


@pytest.mark.parametrize("cambios", [
    {"exp": int(time.time()) - 10},                    # vencido
    {"iss": "https://cognito-idp.us-east-1.amazonaws.com/otro_pool"},
    {"client_id": "otro-cliente"},
    {"token_use": "id"},                               # un id token no sirve para la API
    {"token_use": None},
])
def test_rechaza(verificador, cambios):
    with pytest.raises(NoAutenticado):
        verificador.verificar(_token(**cambios))


def test_rechaza_otra_firma(verificador):
    with pytest.raises(NoAutenticado):
        verificador.verificar(_token(clave=OTRA_CLAVE))


def test_rechaza_basura(verificador):
    with pytest.raises(NoAutenticado):
        verificador.verificar("no-es-un-jwt")


def test_sin_claves_es_servicio_no_disponible():
    v = VerificadorCognito("us-east-1", POOL, [CLIENTE], jwks=JwksFijo(error=jwt.PyJWKClientConnectionError("sin red")))
    with pytest.raises(ServicioNoDisponible):
        v.verificar(_token())


def test_settings_pide_el_pool_y_los_clientes_de_cognito():
    base = {"database_url": "postgresql://x", "bucket_modelos": "m", "bucket_estudios": "e",
            "cola_inferencias_url": "http://sqs/q"}
    assert Settings(**base).cognito_user_pool_id is None
    s = Settings(**base, cognito_user_pool_id=POOL, cognito_client_ids=f"{CLIENTE}, otro")
    assert s.clientes_cognito == [CLIENTE, "otro"]
    with pytest.raises(ValueError):
        Settings(**base, cognito_user_pool_id=POOL)
