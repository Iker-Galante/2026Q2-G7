#!/bin/bash
# userdata.sh — imprime el user data de una plantilla con TUS valores ya adentro, listo para pegar.
#
#   bash infra/userdata.sh lt-app
#   bash infra/userdata.sh lt-worker > /tmp/ud.sh
#
# Por qué existe: un user data se ejecuta en una instancia recién nacida, adentro de AWS. Esa
# máquina no tiene tu terminal ni este repositorio, así que no puede leer infra/entorno.sh: los
# nombres tienen que viajar escritos adentro del script. Rellenarlos es lo que hace esto.
#
# Lo que sale por pantalla es el script; los avisos van por la salida de error, así que
# redirigir a un archivo da el script limpio.
set -euo pipefail
export AWS_PAGER=""
cd "$(dirname "$0")/.."

[ -f infra/entorno.sh ] || {
  echo "Falta infra/entorno.sh — es donde viven los nombres de tus buckets. Crealo con:" >&2
  echo "   cp infra/entorno.example.sh infra/entorno.sh   # y completá los cinco nombres" >&2
  exit 1
}
. infra/entorno.sh

CUAL="${1:?uso: userdata.sh lt-app|lt-worker|lt-eval}"
ORIGEN="infra/userdata/$CUAL.sh"
[ -f "$ORIGEN" ] || { echo "No existe $ORIGEN. Son: lt-app, lt-worker, lt-eval." >&2; exit 2; }

SALIDA=$(cat "$ORIGEN")

# rellenar <hueco> <valor> — no hace nada si este archivo no tiene ese hueco.
rellenar() {
  case "$SALIDA" in *"$1"*) ;; *) return 0 ;; esac
  if [ -z "$2" ] || [ "$2" = "None" ]; then
    echo "ERROR: no pude averiguar el valor de $1." >&2
    exit 1
  fi
  SALIDA=${SALIDA//"$1"/"$2"}
  printf '   %-22s %s\n' "$1" "$2" >&2
}

echo "Rellenando $ORIGEN:" >&2
# Los cinco, aunque hoy las plantillas usen tres: así agregar un hueco nuevo no exige tocar esto.
for _b in DEPLOY WEB MODELOS ESTUDIOS EVALUACION; do
  eval "rellenar __BUCKET_${_b}__ \"\$BUCKET_${_b}\""
done

# Estos dos no están en entorno.sh porque los genera AWS: se preguntan cuando hacen falta.
case "$SALIDA" in *__FS_MODELOS__*)
  rellenar __FS_MODELOS__ "$(aws efs describe-file-systems \
    --query 'FileSystems[?Name==`fs-modelos`].FileSystemId | [0]' --output text 2>/dev/null || true)" ;;
esac
case "$SALIDA" in *__ENDPOINT_RDS__*)
  rellenar __ENDPOINT_RDS__ "$(aws rds describe-db-instances --db-instance-identifier ateneo-db \
    --query 'DBInstances[0].Endpoint.Address' --output text 2>/dev/null || true)" ;;
esac

# Red de seguridad: si quedó un hueco, el script saldría roto y la instancia moriría muda.
if printf '%s\n' "$SALIDA" | grep -q '__[A-Z][A-Z_]*__'; then
  echo "ERROR: quedaron huecos sin llenar:" >&2
  printf '%s\n' "$SALIDA" | grep -o '__[A-Z][A-Z_]*__' | sort -u | sed 's/^/   /' >&2
  exit 1
fi

printf '%s\n' "$SALIDA"

cat >&2 <<AYUDA

Listo. Para pegarlo en la consola, copiá lo de arriba.
Para crear una versión nueva de la plantilla sin pasar por la consola:

   bash infra/userdata.sh $CUAL > /tmp/ud.sh
   printf '{"UserData":"%s"}' "\$(base64 -w0 /tmp/ud.sh)" > /tmp/ltd.json
   aws ec2 create-launch-template-version --launch-template-name $CUAL \\
     --source-version '\$Latest' --launch-template-data file:///tmp/ltd.json \\
     --query 'LaunchTemplateVersion.VersionNumber' --output text
AYUDA
