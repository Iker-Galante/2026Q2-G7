#!/bin/bash
# entorno.sh — los nombres de TUS cinco buckets. Es el único archivo que hay que
# completar para que este repositorio funcione en otra cuenta de AWS.
#
#   cp infra/entorno.example.sh infra/entorno.sh
#   nano infra/entorno.sh          # completá los cinco nombres
#
# Por qué existe: los nombres de bucket son únicos en TODO AWS — no hay dos cuentas
# que puedan tener el mismo. Son lo único de esta guía que cada equipo elige por su
# cuenta, y por eso viven acá y no escritos adentro de los scripts.
#
# Para ver los buckets que ya creaste:  aws s3 ls
# infra/entorno.sh está en .gitignore: es tuyo, no se commitea.

BUCKET_DEPLOY=""        # los zips de código y los tres .env        (guía §04)
BUCKET_WEB=""           # el frontend compilado
BUCKET_MODELOS=""       # los ONNX publicados, con versionado
BUCKET_ESTUDIOS=""      # las radiografías subidas, lifecycle 7 días
BUCKET_EVALUACION=""    # el conjunto reservado, con la policy del endpoint

# --- de acá para abajo no se toca ------------------------------------------
_faltan=""
for _v in BUCKET_DEPLOY BUCKET_WEB BUCKET_MODELOS BUCKET_ESTUDIOS BUCKET_EVALUACION; do
  [ -n "${!_v:-}" ] || _faltan="$_faltan $_v"
done
if [ -n "$_faltan" ]; then
  echo "infra/entorno.sh: falta completar:$_faltan" >&2
  echo "Los buckets que existen en esta cuenta:" >&2
  aws s3 ls 2>/dev/null | awk '{print "   " $3}' >&2
  # return si te sourcearon desde el prompt (no cierra tu terminal), exit si te ejecutaron
  return 1 2>/dev/null || exit 1
fi
unset _faltan _v
