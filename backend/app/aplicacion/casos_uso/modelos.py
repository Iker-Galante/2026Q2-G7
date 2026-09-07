from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ...dominio.contrato import ContratoInvalido, ContratoModelo
from ...dominio.errores import EntradaInvalida
from ...dominio.modelo import Modelo
from ..puertos import CatalogoModelosEnBucket, Reloj, RepositorioModelos


@dataclass(frozen=True)
class ModeloDisponible:
    nombre: str
    version: str
    tipo_estudio: str
    publicado: bool
    modelo_id: UUID | None


class ListarModelosDisponibles:
    """Qué hay en el bucket, y cuáles de esos ya están en el catálogo."""

    def __init__(self, catalogo: CatalogoModelosEnBucket, modelos: RepositorioModelos):
        self._catalogo = catalogo
        self._modelos = modelos

    def ejecutar(self) -> list[ModeloDisponible]:
        publicados = {(m.nombre, m.version): m for m in self._modelos.listar()}
        salida: list[ModeloDisponible] = []
        for ref in self._catalogo.listar():
            existente = publicados.get((ref.nombre, ref.version))
            try:
                tipo = ContratoModelo.desde_json(self._catalogo.leer_contrato(ref.prefix)).tipo_estudio
            except ContratoInvalido as e:
                tipo = f"contrato inválido: {e}"
            salida.append(ModeloDisponible(
                nombre=ref.nombre, version=ref.version, tipo_estudio=tipo,
                publicado=existente is not None, modelo_id=existente.id if existente else None,
            ))
        return sorted(salida, key=lambda m: (m.nombre, m.version))


class PublicarModelo:
    """Simula la subida de un modelo: lo da de alta y lo deja en la cola de evaluación."""

    def __init__(self, catalogo: CatalogoModelosEnBucket, modelos: RepositorioModelos, reloj: Reloj,
                 prefijo_modelos: str):
        self._catalogo = catalogo
        self._modelos = modelos
        self._reloj = reloj
        self._prefijo = prefijo_modelos

    def ejecutar(self, nombre: str, version: str) -> Modelo:
        prefix = f"{self._prefijo}{nombre}/{version}/"
        try:
            contrato = ContratoModelo.desde_json(self._catalogo.leer_contrato(prefix))
        except ContratoInvalido as e:
            raise EntradaInvalida(f"modelo.json inválido: {e}") from e
        if (contrato.nombre, contrato.version) != (nombre, version):
            raise EntradaInvalida(
                f"modelo.json dice {contrato.nombre} v{contrato.version} pero está en el prefijo de {nombre} v{version}"
            )
        ahora = self._reloj.ahora()
        existente = self._modelos.buscar(nombre, version)
        if existente is None:
            modelo = Modelo.publicar(contrato, prefix, ahora)
        else:
            existente.republicar(contrato, ahora)
            modelo = existente
        self._modelos.guardar(modelo)
        return modelo


class ListarModelos:
    def __init__(self, modelos: RepositorioModelos):
        self._modelos = modelos

    def ejecutar(self) -> list[Modelo]:
        return self._modelos.listar()


class ConsultarModelo:
    def __init__(self, modelos: RepositorioModelos):
        self._modelos = modelos

    def ejecutar(self, id: UUID) -> Modelo:
        return self._modelos.obtener(id)
