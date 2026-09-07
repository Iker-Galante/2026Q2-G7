from __future__ import annotations

import copy

import pytest

from app.aplicacion.casos_uso.estudios import CrearEstudio
from app.aplicacion.casos_uso.inferencias import DespacharTrabajo, EncolarInferencia
from app.aplicacion.casos_uso.modelos import ListarModelosDisponibles, PublicarModelo
from app.dominio.errores import Conflicto, EntradaInvalida, FalloDefinitivo, NoEncontrado

from .fakes import (
    AlmacenMemoria, CatalogoMemoria, ClienteInferenciaFalso, RelojFijo,
    RepoEstudiosMemoria, RepoModelosMemoria, RepoTrabajosMemoria,
)

CONTRATO = {
    "nombre": "torax", "version": "1.0.0", "tipo_estudio": "torax-rx", "tarea": "clasificacion",
    "entrada": {"layout": "NCHW", "forma": [1, 3, 224, 224], "espacio_color": "RGB"},
    "salida": {"tipo": "logits", "etiquetas": ["NORMAL", "PNEUMONIA"], "positiva": "PNEUMONIA"},
}
PREFIX = "modelos/torax/1.0.0/"


@pytest.fixture
def mundo():
    class Mundo:
        reloj = RelojFijo()
        modelos = RepoModelosMemoria()
        estudios = RepoEstudiosMemoria()
        trabajos = RepoTrabajosMemoria()
        almacen = AlmacenMemoria()
        catalogo = CatalogoMemoria({PREFIX: copy.deepcopy(CONTRATO)})

        def publicar(self):
            return PublicarModelo(self.catalogo, self.modelos, self.reloj, "modelos/").ejecutar("torax", "1.0.0")

        def crear_estudio(self, tipo="torax-rx", subido=True):
            c = CrearEstudio(self.estudios, self.almacen, self.reloj, 20_000_000, "estudios/").ejecutar(tipo, "image/png", 1234)
            if subido:
                self.almacen.objetos[c.estudio.s3_key] = 1234
            return c.estudio

        def encolar(self, estudio, modelo):
            return EncolarInferencia(self.estudios, self.modelos, self.trabajos, self.almacen, self.reloj).ejecutar(estudio.id, modelo.id)

        def despachar(self, cliente, max_intentos=3):
            return DespacharTrabajo(self.estudios, self.modelos, self.trabajos, cliente, self.reloj,
                                    "b-modelos", "b-estudios", max_intentos)

    return Mundo()


# ---- publicar -----------------------------------------------------------------------

def test_publicar_da_de_alta_en_pendiente(mundo):
    m = mundo.publicar()
    assert m.estado_evaluacion == "pendiente" and m.etiquetas == ["NORMAL", "PNEUMONIA"]
    assert m.s3_prefix == PREFIX and m.accuracy is None


def test_republicar_mientras_esta_pendiente_es_conflicto(mundo):
    mundo.publicar()
    with pytest.raises(Conflicto):
        mundo.publicar()


def test_republicar_un_modelo_evaluado_lo_reencola(mundo):
    m = mundo.publicar()
    m.estado_evaluacion, m.accuracy, m.metricas = "ok", 0.9, {"accuracy": 0.9}
    m2 = mundo.publicar()
    assert m2.id == m.id and m2.estado_evaluacion == "pendiente" and m2.accuracy is None


def test_publicar_contrato_invalido(mundo):
    mundo.catalogo.contratos[PREFIX]["salida"]["etiquetas"] = ["A"]
    with pytest.raises(EntradaInvalida):
        mundo.publicar()
    assert mundo.modelos.listar() == []


def test_publicar_inexistente(mundo):
    with pytest.raises(NoEncontrado):
        PublicarModelo(mundo.catalogo, mundo.modelos, mundo.reloj, "modelos/").ejecutar("otro", "1")


def test_disponibles_marca_publicados(mundo):
    antes = ListarModelosDisponibles(mundo.catalogo, mundo.modelos).ejecutar()
    assert antes[0].publicado is False and antes[0].tipo_estudio == "torax-rx"
    m = mundo.publicar()
    despues = ListarModelosDisponibles(mundo.catalogo, mundo.modelos).ejecutar()
    assert despues[0].publicado is True and despues[0].modelo_id == m.id


# ---- estudios e inferencias ---------------------------------------------------------

def test_crear_estudio_firma_subida(mundo):
    c = CrearEstudio(mundo.estudios, mundo.almacen, mundo.reloj, 20_000_000, "estudios/").ejecutar("torax-rx", "image/jpeg", 10)
    assert c.estudio.s3_key.startswith("estudios/") and c.estudio.s3_key.endswith(".jpg")
    assert c.subida.campos["key"] == c.estudio.s3_key


def test_crear_estudio_mime_o_tamano_invalido(mundo):
    caso = CrearEstudio(mundo.estudios, mundo.almacen, mundo.reloj, 100, "estudios/")
    with pytest.raises(EntradaInvalida):
        caso.ejecutar("torax-rx", "image/gif", 10)
    with pytest.raises(EntradaInvalida):
        caso.ejecutar("torax-rx", "image/png", 101)


def test_encolar_confirma_y_deja_pendiente(mundo):
    m = mundo.publicar()
    e = mundo.crear_estudio()
    t = mundo.encolar(e, m)
    assert t.estado == "pendiente" and t.intentos == 0
    assert mundo.estudios.obtener(e.id).estado == "subido"


def test_encolar_sin_archivo_subido_es_conflicto(mundo):
    m = mundo.publicar()
    e = mundo.crear_estudio(subido=False)
    with pytest.raises(Conflicto):
        mundo.encolar(e, m)


def test_encolar_tipo_distinto(mundo):
    m = mundo.publicar()
    e = mundo.crear_estudio(tipo="cerebro-mri")
    with pytest.raises(EntradaInvalida):
        mundo.encolar(e, m)


# ---- despachar ----------------------------------------------------------------------

def test_despachar_ok(mundo):
    m, e = mundo.publicar(), mundo.crear_estudio()
    mundo.encolar(e, m)
    cliente = ClienteInferenciaFalso()
    t = mundo.trabajos.tomar_pendiente(3)
    mundo.despachar(cliente).ejecutar(t)
    assert t.estado == "ok" and t.worker_id == "worker-1" and t.resultado["prediccion"] == "PNEUMONIA"
    p = cliente.peticiones[0]
    assert p.modelo_prefix == PREFIX and p.estudio_key == e.s3_key and p.modelo_bucket == "b-modelos"


def test_despachar_reintenta_y_agota(mundo):
    m, e = mundo.publicar(), mundo.crear_estudio()
    mundo.encolar(e, m)
    cliente = ClienteInferenciaFalso(fallos_antes_de_responder=10)
    despachar = mundo.despachar(cliente, max_intentos=3)
    estados = []
    while (t := mundo.trabajos.tomar_pendiente(3)) is not None:
        despachar.ejecutar(t)
        estados.append((t.intentos, t.estado))
        ultimo = t
    assert estados == [(1, "pendiente"), (2, "pendiente"), (3, "error")]
    assert "3 intentos" in ultimo.error


def test_despachar_se_recupera_en_el_segundo_intento(mundo):
    m, e = mundo.publicar(), mundo.crear_estudio()
    mundo.encolar(e, m)
    cliente = ClienteInferenciaFalso(fallos_antes_de_responder=1)
    despachar = mundo.despachar(cliente)
    while (t := mundo.trabajos.tomar_pendiente(3)) is not None:
        despachar.ejecutar(t)
        ultimo = t
    assert ultimo.estado == "ok" and ultimo.intentos == 2


def test_fallo_definitivo_no_reintenta(mundo):
    m, e = mundo.publicar(), mundo.crear_estudio()
    mundo.encolar(e, m)
    cliente = ClienteInferenciaFalso(fallos_antes_de_responder=1, error=FalloDefinitivo("imagen ilegible"))
    t = mundo.trabajos.tomar_pendiente(3)
    mundo.despachar(cliente).ejecutar(t)
    assert t.estado == "error" and t.intentos == 1 and mundo.trabajos.tomar_pendiente(3) is None
