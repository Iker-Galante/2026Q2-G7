"""Adaptador que valida los access tokens de Cognito con las claves públicas del user pool.

API Gateway ya valida el token antes de reenviar, pero el ALB es público: este es el control que
no se saltea. Las claves (JWKS) se bajan una vez y quedan en memoria; un token firmado con una
clave nueva hace que se vuelvan a pedir.
"""

from __future__ import annotations

import jwt

from ...dominio.errores import NoAutenticado, ServicioNoDisponible


class VerificadorCognito:
    def __init__(self, region: str, user_pool_id: str, client_id: str, jwks: jwt.PyJWKClient | None = None):
        self._emisor = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self._client_id = client_id
        self._jwks = jwks or jwt.PyJWKClient(f"{self._emisor}/.well-known/jwks.json", timeout=5)

    def verificar(self, token: str) -> str:
        try:
            clave = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, clave, algorithms=["RS256"], issuer=self._emisor,
                                options={"require": ["exp", "iss", "sub", "token_use", "client_id"]})
        except jwt.PyJWKClientConnectionError as e:
            raise ServicioNoDisponible(f"no se pudieron leer las claves de Cognito: {e}") from e
        except jwt.PyJWTError as e:
            raise NoAutenticado(f"token inválido: {e}") from e

        # Un id token también está firmado por el pool, pero no es para llamar a la API.
        if claims["token_use"] != "access":
            raise NoAutenticado("se esperaba un access token")
        if claims["client_id"] != self._client_id:
            raise NoAutenticado("el token es de otro cliente de Cognito")
        return claims["sub"]
