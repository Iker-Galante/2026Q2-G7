# Ateneo en AWS 2.0, como código

La arquitectura de «Ateneo en AWS 2.0» (Entrega 3) entera en Terraform: `terraform apply` levanta
todo en una cuenta limpia del Learner Lab y `terraform destroy` lo borra, imágenes y buckets
incluidos. Quien lo corre no necesita Docker.

| Pieza | Archivo |
|-------|---------|
| VPC 10.0.0.0/16: once subredes en seis capas, una tabla de ruteo por capa, un NAT, NACL de evaluación | `red.tf` |
| Endpoint Gateway de S3 y cuatro de interfaz (`ecr.api`, `ecr.dkr`, `logs`, `sqs`) en subredes propias | `red.tf` |
| Grupos de seguridad encadenados; procesador, worker, evaluador y constructor sin entrada | `seguridad.tf` |
| API Gateway (HTTP API, HTTPS) → VPC Link → ALB interno + WAF | `api.tf`, `balanceador.tf` |
| El autorizador JWT en todo `/api/*` salvo `/api/health` y `/api/publico/*`, que es el catálogo que ve el Visitante | `api.tf`, `backend/app/api/rutas/publico.py` |
| Cognito: cuatro grupos, Hosted UI, Lambda de post-confirmación, admin inicial | `cognito.tf` |
| El login de la clase: sitio en S3 y Lambda en `/callback` | `cognito.tf`, `api.tf`, `lambda/` |
| ECS Fargate: api, procesador, worker, evaluador | `ecs.tf`, `escalado.tf` |
| ECR y el constructor de imágenes | `imagenes.tf`, `plantillas/constructor.sh.tftpl` |
| SQS: `inferencias`, `evaluaciones`, `resultados`, cada una con su cola de fallidos | `colas.tf` |
| RDS PostgreSQL 16 y su URL en Secrets Manager | `datos.tf` |
| Cinco buckets: web (el sitio), modelos, estudios, evaluación, artefactos | `s3.tf`, `scripts/buckets.sh` |
| EFS como caché de modelos de los workers | `efs.tf` |
| SNS y alarmas: colas de fallidos y 5xx del ALB | `alertas.tf` |

## Qué hace `terraform apply`

1. Empaqueta el código del repositorio (backend, frontend, worker, evaluador, `ateneo_ml`) y
   calcula su hash: es la etiqueta de las imágenes.
2. Crea la red, la base, los buckets, las colas, Cognito y API Gateway; sube el paquete al bucket
   de artefactos.
3. Lanza el constructor: una `t3.large` en la capa de aplicación que construye las imágenes
   `backend` y `ml`, las sube a ECR, sube el sitio al bucket web y, con `datos_demo`, siembra el
   modelo de la E2 y el conjunto de 200 casos de Hugging Face. Después se apaga.
4. Espera las imágenes (unos diez minutos la primera vez) y crea los servicios de ECS.
5. Imprime la dirección del sitio y el admin inicial. La verificación es abrir el sitio y entrar.

Un cambio de código produce otro hash: Terraform reemplaza el constructor, se construyen imágenes
nuevas y ECS cambia las tareas de a poco. **Sin cambios, el plan sale vacío.**

## Primer despliegue

En CloudShell, parado en el clon:

```bash
git clone https://github.com/nnicokim/TP-AWS.git ~/ateneo && cd ~/ateneo && git checkout entrega3
bash terraform/scripts/bootstrap-estado.sh            # una vez por cuenta: bucket del estado + backend.hcl
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
nano terraform/terraform.tfvars                       # email_admin y email_alertas
bash terraform/scripts/tf.sh apply
bash terraform/scripts/tf.sh output url
```

Después:

1. Abrí `url`. El admin entra con la contraseña temporal que le mandó Cognito; cualquiera puede
   crear una cuenta de institución o de publicador desde «Ingresar».
2. En `/publicar`, «En el bucket» ya tiene el modelo de demostración: **Publicar**. El evaluador
   arranca solo (de 0 a 1 tarea; uno o dos minutos la primera vez) y lo mide contra el conjunto.
3. En `/consulta`, elegí el modelo y subí una radiografía.

Si pusiste `email_alertas`, AWS manda una confirmación de SNS que hay que aceptar una vez.

**La regla de uso: se destruye al terminar cada sesión de trabajo** (`tf.sh destroy`). Prendido
cuesta unos USD 7 por día; una sesión de tres horas, alrededor de un dólar.

## Login con Cognito

El recorrido de la clase, paso por paso. No es el PKCE de la decisión 08 del HTML: la cátedra pide
este, con el sitio en S3 (cambia también la decisión 11).

| # | Qué pasa | Dónde |
|---|----------|-------|
| 1 | El usuario abre el sitio en S3, por HTTP | `s3.tf` (bucket web como sitio estático) |
| 2 | «Ingresar» (o «crear cuenta») redirige al Hosted UI de Cognito con un `state` al azar | `frontend/src/api/sesion.ts` |
| 3 | Cognito vuelve a `GET /callback` de API Gateway, que es HTTPS | `cognito.tf` (`callback_urls`), `api.tf` |
| 4 | La Lambda canjea el código por los tokens (con el secreto del cliente) y redirige a `http://<sitio>/#access_token=…&id_token=…` | `lambda/callback.py` |
| 5 | El sitio lee los tokens del fragmento, comprueba el `state`, los guarda en `localStorage` y limpia la URL | `sesion.ts` → `recibirDelCallback()` |
| 6 | Cada pedido lleva `Authorization: Bearer <access token>`: API Gateway lo valida y el backend también, y lee los grupos | `frontend/src/api/cliente.ts`, `api.tf`, `backend/app/infraestructura/cognito/` |

- **Por qué el callback no va directo al sitio.** Cognito solo acepta callbacks HTTPS (salvo
  `localhost`), y el sitio de S3 es HTTP: sin CloudFront ni dominio propio no hay certificado.
- **Registro.** Hay un cliente de Cognito por tipo de cuenta (institución, publicador). El sitio
  pone el tipo al principio del `state` para que la Lambda sepa con qué secreto canjear, y la
  Lambda de post-confirmación ve por qué cliente se registró el usuario y lo pone en su grupo
  (`admin_institucion` o `publicador`). Médicos e integrantes llegan por invitación
  (`aws cognito-idp admin-create-user`); los admins, con `email_admin`.
- **Qué guarda el navegador.** Access e id token, una hora. Sin refresh token en la URL: al
  vencer, «Ingresar» vuelve a pasar por Cognito, que recuerda la sesión y no pide la contraseña.

## Restricciones del Learner Lab que este código respeta

- **No crea roles de IAM.** Tareas de ECS, Lambdas y constructor usan `LabRole` o
  `LabInstanceProfile` (se leen con `data`).
- **Los buckets los crea el CLI, no `aws_s3_bucket`.** El lab tiene un deny explícito sobre
  `s3:GetBucketObjectLockConfiguration` en una SCP, y el provider lee esa configuración cada vez
  que refresca un bucket: el apply muere con `AccessDenied` aunque el bucket no use object lock.
  No se arregla con permisos (una SCP no se sobreescribe) ni pineando el provider. Un paso del
  apply llama a `scripts/buckets.sh`, que crea lo que falte y al destruir vacía y borra; todo el
  resto de la configuración de cada bucket la sigue administrando Terraform. Por eso el apply
  necesita el `aws` CLI en la máquina, igual que para esperar las imágenes.
- **Sin CloudFront ni dominio propio.** El HTTPS lo pone API Gateway; el sitio es HTTP.
- **RDS sin Multi-AZ**, solo `us-east-1`, sin instance refresh (ya no hay grupos de EC2).
- **Credenciales de sesión:** se corre desde CloudShell. `scripts/tf.sh` deja el proveedor de AWS
  en `/tmp` para no llenar el giga de `$HOME`.

### Lo que todavía no se probó en un Learner Lab (sección 12 del HTML)

| Qué verificar | Si el lab no lo permite |
|---------------|-------------------------|
| VPC Link de HTTP API hacia un ALB interno | ALB público que solo acepte un encabezado secreto que agrega API Gateway |
| Servicios de Fargate (rol vinculado de ECS) y el escalado de Application Auto Scaling | Las mismas imágenes sobre EC2 con Auto Scaling |
| Cuota de vCPU de Fargate (todo escalado son 8,5 vCPU) | Bajar tamaños y máximos en `ecs.tf` |
| Container Insights en el cluster (publica `RunningTaskCount`, el divisor del backlog por tarea) | `container_insights = false`: worker y procesador escalan por escalones sobre los mensajes visibles |
| WAF asociado a un ALB | `waf_activo = false` |
| Disparador Lambda de Cognito | El backend asigna el grupo en la primera llamada |
| Push a ECR desde EC2 con `LabInstanceProfile` | Construir con Docker en la máquina de quien corre Terraform |
| Bucket web público (bloqueo de acceso público a nivel de cuenta) | Servir el sitio desde la api, detrás de API Gateway |

## Un equipo de varias personas

Los buckets y el dominio de Cognito llevan un sufijo al azar que queda en el estado, así que cada
integrante puede levantar su propio entorno en su lab sin choques. Lo que se comparte es el
repositorio: `terraform.tfvars` y `backend.hcl` son de cada uno y no se commitean.

El hash del código se calcula sobre los archivos tal como están en disco: un clon de Windows con
finales de línea CRLF da otro hash que uno de Linux. Corré Terraform siempre desde CloudShell.

## Pruebas sin cuenta

```bash
cd terraform
terraform init -backend=false
terraform validate
terraform test          # la arquitectura del HTML contra un AWS simulado: red, cómputo, login, variables
```
