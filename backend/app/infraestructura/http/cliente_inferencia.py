"""Cliente del ALB interno. Traduce fallos de red y códigos HTTP a errores del dominio."""

from __future__ import annotations

import httpx

from ...aplicacion.puertos import PeticionInferencia
from ...dominio.errores import FalloDefinitivo, ServicioNoDisponible
from ...dominio.trabajo import ResultadoInferencia


class ClienteInferenciaHttp:
    def __init__(self, base_url: str, timeout_s: float):
        self._cliente = httpx.Client(base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout_s, connect=5.0))

    def inferir(self, p: PeticionInferencia) -> ResultadoInferencia:
        cuerpo = {
            "trabajo_id": str(p.trabajo_id),
            "modelo": {"nombre": p.modelo_nombre, "version": p.modelo_version,
                       "bucket": p.modelo_bucket, "prefix": p.modelo_prefix},
            "estudio": {"bucket": p.estudio_bucket, "key": p.estudio_key},
        }
        try:
            r = self._cliente.post("/inferir", json=cuerpo)
        except httpx.TimeoutException as e:
            raise ServicioNoDisponible(f"el worker no respondió a tiempo: {e.__class__.__name__}") from e
        except httpx.HTTPError as e:
            raise ServicioNoDisponible(f"no se pudo conectar al worker: {e}") from e

        if r.status_code >= 500 or r.status_code in (502, 503, 504):
            raise ServicioNoDisponible(f"el worker respondió {r.status_code}")
        if 400 <= r.status_code < 500:
            detalle = _detalle(r)
            raise FalloDefinitivo(f"el worker rechazó el pedido ({r.status_code}): {detalle}")
        datos = r.json()
        return ResultadoInferencia(
            prediccion=datos["prediccion"],
            probabilidades={k: float(v) for k, v in datos["probabilidades"].items()},
            worker_id=datos.get("worker", "?"),
            duracion_ms=int(datos.get("duracion_ms", 0)),
        )

    def cerrar(self) -> None:
        self._cliente.close()


def _detalle(r: httpx.Response) -> str:
    try:
        d = r.json()
        return d.get("detalle") or d.get("detail") or r.text
    except ValueError:
        return r.text[:200]
