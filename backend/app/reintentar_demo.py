"""Recuperación explícita de la demo; nunca borra otros modelos ni resultados válidos."""
import json

from tools.demo_assets import MODELO_DIR, NOMBRE, VERSION

from .aplicacion.casos_uso.modelos import PublicarModelo
from .aplicacion.puertos import PeticionEvaluacion
from .config import Settings
from .demo import CLAVE, ConexionPrestada, InicializarDemo, OutboxDemo
from .infraestructura.aws import cliente_s3, cliente_sqs
from .infraestructura.postgres.conexion import crear_pool
from .infraestructura.postgres.repositorios import RepositorioModelosPostgres
from .infraestructura.reloj import RelojSistema
from .infraestructura.s3.catalogo_modelos import CatalogoModelosS3


def main():
    s = Settings()
    if not s.datos_demo:
        raise SystemExit("La demo está desactivada")
    pool = crear_pool(s.database_url)
    pool.open(wait=True)
    s3, sqs = cliente_s3(s.aws_region), cliente_sqs(s.aws_region)
    try:
        with pool.connection() as conn:
            conn.execute("select pg_advisory_xact_lock(82082026)")
            repo = RepositorioModelosPostgres(ConexionPrestada(conn))
            m = repo.buscar(NOMBRE, VERSION)
            if m is None:
                raise SystemExit("Primero completá la preparación de artefactos")
            contrato = json.loads((MODELO_DIR / "modelo.json").read_text())
            if m.contrato != contrato:
                raise SystemExit("El contrato existente pertenece a otro modelo")
            if m.estado_evaluacion in ("ok", "en_curso"):
                raise SystemExit("La demo está lista o evaluándose: no se modifica")
            conn.execute("delete from demo_inicializacion where clave=%s", (CLAVE,))
            outbox = OutboxDemo(conn)
            if m.estado_evaluacion == "error":
                PublicarModelo(CatalogoModelosS3(s3, s.bucket_modelos), repo, RelojSistema(),
                               s.prefijo_modelos, outbox).ejecutar(NOMBRE, VERSION)
            else:
                outbox.enviar(PeticionEvaluacion.de(m))
        InicializarDemo(pool, s3, sqs, s).ejecutar()
        print("Recuperación solicitada. Usá tools/esperar_modelo.py para verificar.")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
