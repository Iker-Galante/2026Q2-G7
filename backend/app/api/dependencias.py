"""Composition root: el único módulo que instancia adaptadores.

`Contenedor` arma el grafo una vez por proceso; las funciones `Depends` de abajo
son lo que reciben los routers. Los tests reemplazan estas funciones con
`app.dependency_overrides`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import boto3
from botocore.config import Config as BotoConfig
from fastapi import Depends, Request

from ..aplicacion.casos_uso.estudios import CrearEstudio
from ..aplicacion.casos_uso.inferencias import (
    ConsultarTrabajo, DespacharTrabajo, EncolarInferencia, ReenviarPendientes,
)
from ..aplicacion.casos_uso.modelos import (
    ConsultarModelo, ListarModelos, ListarModelosDisponibles, PrepararSubidaModelo, PublicarModelo,
)
from ..aplicacion.despachador import Despachador
from ..aplicacion.puertos import VerificadorTokens
from ..aplicacion.reenviador import Reenviador
from ..config import Settings
from ..dominio.errores import NoAutenticado
from ..infraestructura.cognito.verificador import VerificadorCognito
from ..infraestructura.http.cliente_inferencia import ClienteInferenciaHttp
from ..infraestructura.postgres.conexion import crear_pool
from ..infraestructura.postgres.repositorios import (
    RepositorioEstudiosPostgres, RepositorioModelosPostgres, RepositorioTrabajosPostgres,
)
from ..infraestructura.reloj import RelojSistema
from ..infraestructura.s3.almacen_estudios import AlmacenEstudiosS3
from ..infraestructura.s3.catalogo_modelos import CatalogoModelosS3
from ..infraestructura.sqs.cola_inferencias import ColaInferenciasSqs


@dataclass
class Contenedor:
    settings: Settings
    listar_disponibles: ListarModelosDisponibles
    preparar_subida: PrepararSubidaModelo
    publicar_modelo: PublicarModelo
    listar_modelos: ListarModelos
    consultar_modelo: ConsultarModelo
    crear_estudio: CrearEstudio
    encolar_inferencia: EncolarInferencia
    consultar_trabajo: ConsultarTrabajo
    despachador: Despachador | Reenviador      # el bucle de fondo: uno u otro según el modo
    pool: object
    cliente_inferencia: ClienteInferenciaHttp | None
    verificador: VerificadorTokens | None      # None = sin Cognito: todos anónimos

    def abrir(self) -> None:
        self.pool.open()          # type: ignore[attr-defined]

    def cerrar(self) -> None:
        if self.cliente_inferencia is not None:
            self.cliente_inferencia.cerrar()
        self.pool.close()         # type: ignore[attr-defined]


def armar(settings: Settings) -> Contenedor:
    pool = crear_pool(settings.database_url)
    s3 = boto3.client(
        "s3",
        region_name=settings.aws_region,
        config=BotoConfig(connect_timeout=5, read_timeout=15, retries={"max_attempts": 2},
                          signature_version="s3v4",
                          s3={"addressing_style": "path" if os.environ.get("AWS_ENDPOINT_URL") else "auto"}),
    )
    reloj = RelojSistema()

    modelos = RepositorioModelosPostgres(pool)
    estudios = RepositorioEstudiosPostgres(pool)
    trabajos = RepositorioTrabajosPostgres(pool)
    almacen = AlmacenEstudiosS3(s3, settings.bucket_estudios, settings.s3_url_publica)
    catalogo = CatalogoModelosS3(s3, settings.bucket_modelos, settings.prefijo_modelos, settings.s3_url_publica)
    if settings.modo_inferencia == "sqs":
        sqs = boto3.client("sqs", region_name=settings.aws_region,
                           config=BotoConfig(connect_timeout=5, read_timeout=10, retries={"max_attempts": 3}))
        cola = ColaInferenciasSqs(sqs, settings.cola_inferencias_url)
        cliente = None
        fondo: Despachador | Reenviador = Reenviador(ReenviarPendientes(
            trabajos, estudios, modelos, cola, settings.bucket_modelos, settings.bucket_estudios,
            settings.reenvio_minutos, settings.vencimiento_en_curso_minutos))
    else:
        cola = None
        cliente = ClienteInferenciaHttp(settings.inferencia_url, settings.timeout_inferencia_s)
        despachar = DespacharTrabajo(estudios, modelos, trabajos, cliente, reloj,
                                     settings.bucket_modelos, settings.bucket_estudios, settings.max_intentos)
        fondo = Despachador(trabajos, despachar, settings.intervalo_despacho_s,
                            settings.max_intentos, settings.huerfanos_minutos)

    verificador = None
    if settings.cognito_user_pool_id and settings.cognito_client_id:
        verificador = VerificadorCognito(settings.aws_region, settings.cognito_user_pool_id,
                                         settings.cognito_client_id)

    return Contenedor(
        settings=settings,
        listar_disponibles=ListarModelosDisponibles(catalogo, modelos),
        preparar_subida=PrepararSubidaModelo(catalogo, settings.max_bytes_modelo, settings.prefijo_modelos),
        publicar_modelo=PublicarModelo(catalogo, modelos, reloj, settings.prefijo_modelos),
        listar_modelos=ListarModelos(modelos),
        consultar_modelo=ConsultarModelo(modelos),
        crear_estudio=CrearEstudio(estudios, almacen, reloj, settings.max_bytes_estudio, settings.prefijo_estudios),
        encolar_inferencia=EncolarInferencia(estudios, modelos, trabajos, almacen, reloj,
                                             cola, settings.bucket_modelos, settings.bucket_estudios),
        consultar_trabajo=ConsultarTrabajo(trabajos),
        despachador=fondo,
        pool=pool,
        cliente_inferencia=cliente,
        verificador=verificador,
    )


# ---- lo que reciben los routers -----------------------------------------------------

def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


def dep_listar_disponibles(request: Request) -> ListarModelosDisponibles:
    return contenedor(request).listar_disponibles


def dep_preparar_subida(request: Request) -> PrepararSubidaModelo:
    return contenedor(request).preparar_subida


def dep_publicar_modelo(request: Request) -> PublicarModelo:
    return contenedor(request).publicar_modelo


def dep_listar_modelos(request: Request) -> ListarModelos:
    return contenedor(request).listar_modelos


def dep_consultar_modelo(request: Request) -> ConsultarModelo:
    return contenedor(request).consultar_modelo


def dep_crear_estudio(request: Request) -> CrearEstudio:
    return contenedor(request).crear_estudio


def dep_encolar_inferencia(request: Request) -> EncolarInferencia:
    return contenedor(request).encolar_inferencia


def dep_consultar_trabajo(request: Request) -> ConsultarTrabajo:
    return contenedor(request).consultar_trabajo


def dep_verificador(request: Request) -> VerificadorTokens | None:
    return contenedor(request).verificador


def usuario_actual(request: Request, verificador: VerificadorTokens | None = Depends(dep_verificador)) -> str:
    """El sub del access token de Cognito (Authorization: Bearer …). Sin Cognito, anónimo."""
    if verificador is None:
        return "anonimo"
    tipo, _, token = request.headers.get("authorization", "").partition(" ")
    if tipo.lower() != "bearer" or not token.strip():
        raise NoAutenticado("falta el token: ingresá de nuevo")
    return verificador.verificar(token.strip())
