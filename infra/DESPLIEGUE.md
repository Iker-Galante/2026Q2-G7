# Cómo llevar este código al AWS Academy

Mapa entre el repositorio y la guía `ateneo-paso-a-paso.html`: en qué sección se despliega cada
pieza, qué archivo del repo es, y qué tiene que decir cada `.env`. La regla de la guía se
mantiene: **la infraestructura no cambia**; solo cambia lo que hay adentro de los zips y del
bucket web.

## 0. Antes de empezar

| Qué | Dónde | Sección de la guía |
|-----|-------|--------------------|
| Clon del repo en CloudShell | `~/ateneo` (`git clone …` y después `git pull`) | §11 «La carpeta de scripts» |
| Scripts de infra con permiso | `chmod +x ~/ateneo/infra/*.sh` | §11 |
| Nombres de bucket | los ejemplos usan `-g7`; en `infra/desplegar.sh` se cambian con `DEPLOY_BUCKET` y `WEB_BUCKET` | §04 |

Vas por el paso 9. Todo lo que sigue asume las secciones 02 a 08 hechas (red, SG, buckets,
RDS, ALB externo con `asg-app`, EFS, AMI dorada, ALB interno con `asg-inf`).

## 1. Qué va a cada capa

| Pieza del repo | Capa | Se aplica en | Cómo llega | Cómo se activa |
|----------------|------|--------------|------------|----------------|
| `migraciones/001_inicial.sql` + `tools/migrar.py` | base | **§11, fila «Esquema de la base»** (antes que nada) | Session Manager a una instancia app | `set -a; . /etc/ateneo.env; set +a; cd /opt/ateneo && ../venv/bin/python tools/migrar.py` (ver §3) |
| `backend/` | app (`asg-app`) | **§7.1 «Después · con el código real»** | `bash infra/desplegar.sh backend` → `s3://…-deploy/backend/backend-latest.zip` | `bash infra/refrescar.sh asg-app` |
| `frontend/` (build) | app, servido por el backend en `/` | **§10 «Después · el frontend real»** | `bash infra/desplegar.sh frontend` → `s3://…-web/` | `bash infra/refrescar.sh asg-app` (las instancias copian el bucket al nacer) |
| `worker/` + `ateneo_ml/` | inferencia (`asg-inf`) | **§8.3, paso 1 («después, el zip desde el clon»)** | `bash infra/desplegar.sh worker` → `s3://…-deploy/worker/worker-latest.zip` | `bash infra/refrescar.sh asg-inf` |
| `evaluador/` + `ateneo_ml/` | evaluación (`eval-1`) | **§9.5 «Después · el evaluador de verdad»** | el mismo `worker-latest.zip` | versión nueva de `lt-eval` con `infra/userdata/lt-eval.sh` · terminar `eval-1` · `run-instances` |
| `infra/userdata/*.sh` | plantillas | §7.2 (`lt-app`), §8.3 (`lt-worker`), §9.1/§9.5 (`lt-eval`) | copiar y pegar en **User data** | nueva versión de la plantilla → el grupo en `Latest` → `refrescar.sh` |
| `infra/*.env.example` | config | §7.1, §8.3, §9.5 | `aws s3 cp` a `s3://…-deploy/config/` | mismo `refrescar.sh` de la capa |

El user data de `lt-app` y el de `lt-worker` son **los mismos de la guía**: el código real no
los cambia. El de `lt-eval` es el «Después» de la §9.5. Están en `infra/userdata/` para tenerlos
versionados.

### Dos cambios respecto de la guía

1. **El zip del worker lleva tres carpetas, no dos:** `worker/ evaluador/ ateneo_ml/`.
   `infra/desplegar.sh worker` ya lo hace así. `ateneo_ml` es el paquete compartido que garantiza
   que el evaluador mide con el mismo preprocesamiento con el que infiere el worker.

2. **La AMI dorada necesita `numpy` fijado por debajo de 2.** La línea de la §8.2 instala
   `numpy` a secas, que hoy trae la versión 2, y `onnxruntime==1.18.0` está compilado contra la 1:
   el worker arranca y muere con `AttributeError: _ARRAY_API not found`, sin decir por qué. La
   línea correcta es:

   ```bash
   /opt/venv/bin/pip install -q onnxruntime==1.18.0 "numpy<2" pillow pydicom boto3 fastapi uvicorn "psycopg[binary]"
   ```

   Es un solo carácter de diferencia y cuesta una tarde de diagnóstico, porque a los workers no se
   entra y el síntoma es una instancia `unhealthy` en loop.

## 2. Los `.env`, uno por capa

Se suben **fuera del repo** (`.gitignore` los excluye) a `s3://ateneo-deploy-g7/config/`. Cada
instancia los baja a `/etc/ateneo.env` al arrancar. Cambiar un `.env` = volver a subirlo +
`refrescar.sh` de esa capa.

### `config/backend.env` (capa app) — `infra/backend.env.example`

```
DATABASE_URL=postgresql://ateneo:LA_CLAVE@ateneo-db.abc123.us-east-1.rds.amazonaws.com:5432/ateneo   # §05, endpoint de RDS
AWS_REGION=us-east-1
BUCKET_MODELOS=ateneo-modelos-g7
BUCKET_ESTUDIOS=ateneo-estudios-g7
INFERENCIA_URL=http://internal-alb-ateneo-int-XXXX.us-east-1.elb.amazonaws.com:8081                  # §8.4, DNS del ALB interno, con puerto
ORIGEN_WEB=http://alb-ateneo-XXXXXXXX.us-east-1.elb.amazonaws.com                                    # §7.4, DNS del ALB externo
```

### `config/worker.env` (capa inferencia) — `infra/worker.env.example`

```
AWS_REGION=us-east-1
MODELOS_DIR=/mnt/modelos
```

### `config/evaluador.env` (`eval-1`) — `infra/evaluador.env.example`

```
AWS_REGION=us-east-1
BUCKET_EVALUACION=ateneo-evaluacion-g7
BUCKET_MODELOS=ateneo-modelos-g7
DATABASE_URL=postgresql://ateneo:LA_CLAVE@ateneo-db.abc123.us-east-1.rds.amazonaws.com:5432/ateneo
```

## 3. El orden, paso a paso

Es el orden de la §15 de la guía («un cambio por vez para saber cuál rompió»).

1. **Los `.env` reales** a `s3://…-deploy/config/` (los tres de arriba).
2. **El backend.** `bash infra/desplegar.sh backend` · `bash infra/refrescar.sh asg-app`.
   Esperar `healthy` en `tg-app` (5-8 min). `curl http://<alb>/api/health` tiene que contestar.
3. **El esquema.** La base solo se alcanza desde adentro de la VPC (§05), así que el SQL viaja
   por S3 y se aplica desde una instancia app. En CloudShell:
   ```bash
   aws s3 cp migraciones/001_inicial.sql s3://ateneo-deploy-g7/migraciones/001_inicial.sql
   ```
   Session Manager a una instancia app (§6.1) y ahí:
   ```bash
   sudo -i
   set -a; . /etc/ateneo.env; set +a
   aws s3 cp s3://ateneo-deploy-g7/migraciones/001_inicial.sql /tmp/
   psql "$DATABASE_URL" -f /tmp/001_inicial.sql
   psql "$DATABASE_URL" -c '\dt'      # tienen que estar modelo, estudio, trabajo
   ```
   (`psql` está en la instancia porque el user data instala `postgresql16`.)
4. **El worker.** `bash infra/desplegar.sh worker` · `bash infra/refrescar.sh asg-inf`. Verificar
   `healthy` en `tg-inf` como en §8.4.
5. **El frontend.** `bash infra/desplegar.sh frontend` · `bash infra/refrescar.sh asg-app`.
   Abrir `http://<alb>/`: tiene que aparecer la pantalla «Laboratorio» con «API: ok».
6. **El modelo a S3** (la «subida a mano», D2 de specs). Desde CloudShell, parado en `~/ateneo`,
   sin gastar disco:
   ```bash
   P=s3://ateneo-modelos-g7/modelos/torax-rx-neumonia/1.0.0
   curl -sL https://huggingface.co/Rhishamah/mediscan-pneumonia/resolve/main/mediscan_pneumonia.onnx | aws s3 cp - $P/modelo.onnx
   python3 tools/descargar_modelo.py --contrato | aws s3 cp - $P/modelo.json
   aws s3 ls $P/            # tienen que estar los dos, el .onnx de unos 16 MB
   ```
7. **El conjunto reservado.** No hace falta cuenta de Kaggle: el dataset se baja de la API pública
   de Hugging Face. En tu máquina (o en una instancia app, que tiene salida por el NAT):
   ```bash
   python tools/preparar_conjunto.py --hf hf-vision/chest-xray-pneumonia --split test \n          --por-clase 100 --salida ./tmp/torax-rx/v1
   ```
   Subir la carpeta `v1` por la consola de S3 a `ateneo-evaluacion-g7/torax-rx/` (§04, «Después ·
   el conjunto real») y borrar los dos archivos de mentira. Son 200 PNG, unos 40 MB.
8. **`eval-1`.** Subir `config/evaluador.env`; crear una versión nueva de `lt-eval` con
   `infra/userdata/lt-eval.sh` (reemplazando el endpoint de RDS); terminar la instancia vieja y
   `aws ec2 run-instances --launch-template LaunchTemplateName=lt-eval,Version='$Latest'`.
   Leer el boletín: `aws ec2 get-console-output --instance-id i-… --latest --output text | grep RESULTADO`.
9. **Apretar «Publicar modelo»** en la pantalla. En 2-4 minutos la tarjeta muestra la accuracy.
   Si queda en `pendiente` más de un minuto, `eval-1` no está tomando la cola: mirá su log de
   arranque (§9.3) y que `evaluador.env` tenga la `DATABASE_URL` correcta.
10. **Inferir** con cualquier radiografía de tórax, por ejemplo una de `tmp/torax-rx/v1/casos/`.
    El trabajo pasa por `pendiente → en_curso → ok` y la pantalla muestra el `worker_id`.

## 4. Qué se vuelve a desplegar cuando cambia qué

| Cambió | Comando | Después |
|--------|---------|---------|
| `backend/` | `desplegar.sh backend` | `refrescar.sh asg-app` |
| `frontend/` | `desplegar.sh frontend` | `refrescar.sh asg-app` |
| `worker/` o `ateneo_ml/` | `desplegar.sh worker` | `refrescar.sh asg-inf` **y** terminar + relanzar `eval-1` (usa el mismo zip) |
| `evaluador/` | `desplegar.sh worker` | terminar + relanzar `eval-1` |
| un `.env` | `aws s3 cp` a `config/` | `refrescar.sh` de esa capa (o relanzar `eval-1`) |
| `migraciones/` | subir el SQL y aplicarlo desde una instancia app | nada |
| dependencias del worker/evaluador | nueva AMI (§8.2, `pip install` con la lista nueva) | nueva versión de `lt-worker` y `lt-eval` |

## 5. Verificaciones rápidas

```bash
ALB=$(aws elbv2 describe-load-balancers --names alb-ateneo --query 'LoadBalancers[0].DNSName' --output text)
curl -s http://$ALB/api/health; echo
curl -s http://$ALB/api/modelos/disponibles; echo        # tiene que listar torax-rx-neumonia 1.0.0
curl -s -X POST http://$ALB/api/modelos/publicar -H 'content-type: application/json' \
     -d '{"nombre":"torax-rx-neumonia","version":"1.0.0"}'; echo
curl -s http://$ALB/api/modelos | python3 -m json.tool | grep -E '"(estado_evaluacion|accuracy)"'
```

Y las pruebas de la demo de la guía (§13) siguen valiendo tal cual: la 4 y la 5 ahora se hacen
desde la pantalla (varias inferencias seguidas muestran `worker_id` distintos).
