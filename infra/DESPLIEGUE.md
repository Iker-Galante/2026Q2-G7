# Cómo llevar este código al AWS Academy

Mapa entre el repositorio y la guía `ateneo-paso-a-paso.html`: en qué sección se despliega cada
pieza, qué archivo del repo es, y qué tiene que decir cada `.env`. La regla de la guía se
mantiene: **la infraestructura no cambia**; solo cambia lo que hay adentro de los zips y del
bucket web.

## 0. Antes de empezar

| Qué | Dónde | Sección de la guía |
|-----|-------|--------------------|
| Clon del repo en CloudShell | `~/ateneo` (`git clone …` y después `git pull`) | §04 |
| Scripts de infra con permiso | `chmod +x ~/ateneo/infra/*.sh` | §04 |
| **Los nombres de tus buckets** | `cp infra/entorno.example.sh infra/entorno.sh` y completar los cinco | §04 |

**`infra/entorno.sh` es el único archivo que hay que completar para que este repositorio funcione
en otra cuenta.** Los nombres de bucket son únicos en todo AWS, así que son lo único que cada
equipo elige por su cuenta; todo lo demás (`asg-app`, `ateneo-db`, `lt-eval`, los CIDR) es por
cuenta y la guía lo dicta igual para todos. Ni los scripts ni las plantillas llevan un nombre de
bucket escrito adentro: lo leen de ahí.  `infra/entorno.sh` está en `.gitignore`.

Vas por el paso 9. Todo lo que sigue asume las secciones 02 a 08 hechas (red, SG, buckets,
RDS, ALB externo con `asg-app`, EFS, AMI dorada, ALB interno con `asg-inf`).

## 1. Qué va a cada capa

| Pieza del repo | Capa | Se aplica en | Cómo llega | Cómo se activa |
|----------------|------|--------------|------------|----------------|
| `migraciones/001_inicial.sql` | base | **§15, paso 4** (antes que el resto) | por S3, y se aplica con `psql` desde una instancia app por Session Manager | el paso completo está en la §3 de acá abajo |
| `backend/` | app (`asg-app`) | **§7.1 «Después · con el código real»** | `bash infra/desplegar.sh backend` → `s3://…-deploy/backend/backend-latest.zip` | `bash infra/refrescar.sh asg-app` |
| `frontend/` (build) | app, servido por el backend en `/` | **§10 «Después · el frontend real»** | `bash infra/desplegar.sh frontend` → `s3://…-web/` | `bash infra/refrescar.sh asg-app` (las instancias copian el bucket al nacer) |
| `worker/` + `ateneo_ml/` | inferencia (`asg-inf`) | **§8.3, paso 1 («después, el zip desde el clon»)** | `bash infra/desplegar.sh worker` → `s3://…-deploy/worker/worker-latest.zip` | `bash infra/refrescar.sh asg-inf` |
| `evaluador/` + `ateneo_ml/` | evaluación (`eval-1`) | **§9.5 «Después · el evaluador de verdad»** | el mismo `worker-latest.zip` | versión nueva de `lt-eval` con `infra/userdata/lt-eval.sh` · terminar `eval-1` · `run-instances` |
| `infra/userdata/*.sh` | plantillas | §7.2 (`lt-app`), §8.3 (`lt-worker`), §9.1/§9.5 (`lt-eval`) | **`bash infra/userdata.sh lt-worker`** y pegar la salida en **User data** | nueva versión de la plantilla → el grupo en `Latest` → `refrescar.sh` |
| los tres `.env` | config | §7.1, §8.3, §9.5 | **`bash infra/generar-env.sh`** | mismo `refrescar.sh` de la capa |

Los tres user data están en `infra/userdata/` con **huecos** en vez de valores: `__BUCKET_DEPLOY__`,
`__BUCKET_WEB__`, `__BUCKET_EVALUACION__`, `__FS_MODELOS__` y `__ENDPOINT_RDS__`. No se pegan tal
cual: los rellena `bash infra/userdata.sh <plantilla>`, que toma los buckets de `infra/entorno.sh`
y pregunta el id del EFS y el endpoint de la base a la propia AWS. Si algún hueco quedara sin
llenar, el script corta con error en vez de dejarte pegar un script roto.

Existen porque un user data se ejecuta en una instancia recién nacida adentro de AWS: esa máquina
no tiene tu CloudShell ni este repositorio, así que no puede leer `entorno.sh`. Los nombres tienen
que viajar escritos adentro, y rellenarlos antes de pegar es la única forma.

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

Se suben **fuera del repo** (`.gitignore` los excluye) a `s3://$BUCKET_DEPLOY/config/`. Cada
instancia los baja a `/etc/ateneo.env` al arrancar. Cambiar un `.env` = volver a subirlo +
`refrescar.sh` de esa capa.

**No se escriben a mano:** `bash infra/generar-env.sh` arma los tres con los buckets de
`infra/entorno.sh`, averigua solo el endpoint de RDS y los DNS de los dos balanceadores, y los
sube. Lo único que se tipea es la contraseña de la base, que además codifica para la URL (una
contraseña con `@`, `/` o `#` partiría la `DATABASE_URL` en dos). Lo que sigue es la referencia
de qué lleva cada archivo.

### `config/backend.env` (capa app) — `infra/backend.env.example`

```
DATABASE_URL=postgresql://ateneo:LA_CLAVE@ENDPOINT_DE_TU_RDS:5432/ateneo                             # §05, endpoint de RDS
AWS_REGION=us-east-1
BUCKET_MODELOS=<tu bucket de modelos>
BUCKET_ESTUDIOS=<tu bucket de estudios>
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
BUCKET_EVALUACION=<tu bucket de evaluación>
BUCKET_MODELOS=<tu bucket de modelos>
DATABASE_URL=postgresql://ateneo:LA_CLAVE@ENDPOINT_DE_TU_RDS:5432/ateneo
```

## 3. El orden, paso a paso

Es el orden de la §15 de la guía («un cambio por vez para saber cuál rompió»).

1. **Los `.env` reales.** `bash infra/generar-env.sh` — arma los tres y los sube.
2. **El backend.** `bash infra/desplegar.sh backend` · `bash infra/refrescar.sh asg-app`.
   Esperar `healthy` en `tg-app` (5-8 min). `curl http://<alb>/api/health` tiene que contestar.
3. **El esquema.** La base solo se alcanza desde adentro de la VPC (§05), así que el SQL viaja
   por S3 y se aplica desde una instancia app. En CloudShell:
   ```bash
   . infra/entorno.sh
   aws s3 cp migraciones/001_inicial.sql s3://$BUCKET_DEPLOY/migraciones/001_inicial.sql
   ```
   Session Manager a una instancia app (§6.1) y ahí:
   ```bash
   sudo -i
   set -a; . /etc/ateneo.env; set +a
   aws s3 cp s3://<tu bucket de deploy>/migraciones/001_inicial.sql /tmp/
   psql "$DATABASE_URL" -f /tmp/001_inicial.sql
   psql "$DATABASE_URL" -c '\dt'      # tienen que estar modelo, estudio, trabajo
   ```
   (`psql` está en la instancia porque el user data instala `postgresql16`.)
4. **El worker.** `bash infra/desplegar.sh worker` · `bash infra/refrescar.sh asg-inf`. Verificar
   `healthy` en `tg-inf` como en §8.4.
5. **El frontend.** `bash infra/desplegar.sh frontend` · `bash infra/refrescar.sh asg-app`.
   Abrir `http://<alb>/`: tiene que aparecer la portada de Ateneo con «API ok» en la barra, y
   `/publicar` y `/consulta` tienen que cargar también al recargar el navegador.

   **CORS de los dos buckets que reciben subidas del navegador** (estudios y modelos):

   ```bash
   bash infra/cors.sh http://<dns-del-alb>
   ```

   Sin esto, subir un estudio o un modelo falla con un error de red que no dice por qué. Se corre
   una vez, y de nuevo solo si cambia el DNS del balanceador. El rol de las instancias app además
   tiene que poder `s3:PutObject` en el bucket de modelos: la API escribe ahí el `modelo.json`
   validado (`LabRole` ya lo permite).
6. **El modelo.** El camino del producto es subirlo desde `/publicar` con su `modelo.json`: para
   eso alcanza con tener los dos archivos en tu máquina
   (`python3 tools/descargar_modelo.py --solo-descargar`). Si preferís sembrar el bucket desde
   CloudShell, sin gastar disco y sin navegador:
   ```bash
   . infra/entorno.sh
   P=s3://$BUCKET_MODELOS/modelos/torax-rx-neumonia/1.0.0
   curl -sL https://huggingface.co/Rhishamah/mediscan-pneumonia/resolve/main/mediscan_pneumonia.onnx | aws s3 cp - $P/modelo.onnx
   python3 tools/descargar_modelo.py --contrato | aws s3 cp - $P/modelo.json
   aws s3 ls $P/            # tienen que estar los dos, el .onnx de unos 16 MB
   ```
7. **El conjunto reservado.** No hace falta cuenta de Kaggle: el dataset se baja de la API pública
   de Hugging Face. En tu máquina (o en una instancia app, que tiene salida por el NAT):
   ```bash
   python tools/preparar_conjunto.py --hf hf-vision/chest-xray-pneumonia --split test \
          --por-clase 100 --salida ./tmp/torax-rx/v1
   ```
   Subir la carpeta `v1` por la consola de S3 a `<tu bucket de evaluación>/torax-rx/` (§04, «Después ·
   el conjunto real») y borrar los dos archivos de mentira. Son 200 PNG, unos 40 MB.
8. **`eval-1`.** Crear una versión nueva de `lt-eval` con `bash infra/userdata.sh lt-eval`
   (rellena los buckets y el endpoint de RDS solo); terminar la instancia vieja y
   `aws ec2 run-instances --launch-template LaunchTemplateName=lt-eval,Version='$Latest'`.
   Leer el boletín: `aws ec2 get-console-output --instance-id i-… --latest --output text | grep RESULTADO`.
9. **Subir y publicar** en `/publicar` (o «Publicar» sobre el modelo que ya sembraste en el paso
   6). En 2-4 minutos la tarjeta muestra la accuracy.
   Si queda en `pendiente` más de un minuto, `eval-1` no está tomando la cola: mirá su log de
   arranque (§9.3) y que `evaluador.env` tenga la `DATABASE_URL` correcta.
10. En `/consulta`, **Consultar** con cualquier radiografía de tórax, por ejemplo una de
    `tmp/torax-rx/v1/casos/`.
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
| **un nombre de bucket** | editar `infra/entorno.sh` | volver a generar los `.env` y los user data que lo usen, y refrescar |

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
