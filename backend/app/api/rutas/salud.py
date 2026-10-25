import socket

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Lo consulta el balanceador: rápido y sin tocar la base."""
    return {"ok": True}


@router.get("/api/health")
def api_health() -> dict:
    """Lo consultás vos desde afuera: el hostname muestra al ALB alternando instancias."""
    return {"ok": True, "instancia": socket.gethostname()}
