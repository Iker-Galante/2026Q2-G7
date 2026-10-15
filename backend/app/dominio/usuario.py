"""Quién hace el pedido. La API lo arma desde el access token de Cognito."""

from __future__ import annotations

from dataclasses import dataclass

# Un grupo de Cognito por rol (terraform/cognito.tf). La matriz de permisos por rol todavía no
# se aplica: la API autentica a todos por igual y deja los grupos a mano para cuando llegue.
GRUPOS = ("medico", "admin_institucion", "publicador", "admin_plataforma")


@dataclass(frozen=True)
class Usuario:
    sub: str
    grupos: tuple[str, ...] = ()

    @staticmethod
    def anonimo() -> "Usuario":
        """Sin Cognito configurado (docker compose, tests)."""
        return Usuario(sub="anonimo")
