# Los tres .env (guía §2 de DESPLIEGUE.md), escritos por Terraform en s3://<deploy>/config/.
# Reemplazan a generar-env.sh: el endpoint de RDS, los DNS de los balanceadores y la contraseña
# salen del propio estado, así que nunca quedan desfasados. La contraseña vive en el estado
# (bucket privado y cifrado) y en estos objetos, nunca en un user data ni en el repositorio.

locals {
  alb_int_dns = var.encendido && local.http ? aws_lb.inf[0].dns_name : ""

  env_backend = {
    DATABASE_URL    = local.database_url
    AWS_REGION      = var.region
    BUCKET_MODELOS  = local.buckets.modelos
    BUCKET_ESTUDIOS = local.buckets.estudios
    # El backend de hoy la exige. En modo sqs no hay ALB interno y la que manda es la cola.
    INFERENCIA_URL       = local.alb_int_dns != "" ? "http://${local.alb_int_dns}:8081" : "http://sin-alb-interno.invalid:8081"
    ORIGEN_WEB           = local.url_sitio
    MODO_INFERENCIA      = var.modo_inferencia
    COLA_INFERENCIAS_URL = aws_sqs_queue.inferencias.url
    # El backend vuelve a validar el access token: al ALB se puede llegar sin pasar por API Gateway.
    COGNITO_USER_POOL_ID = aws_cognito_user_pool.ateneo.id
    COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.web.id
  }

  env_worker = merge(
    {
      AWS_REGION  = var.region
      MODELOS_DIR = "/mnt/modelos"
    },
    # Modo sqs: el worker consume la cola y escribe el resultado en la base (sg-data ya lo deja).
    local.sqs ? {
      MODO_INFERENCIA      = "sqs"
      COLA_INFERENCIAS_URL = aws_sqs_queue.inferencias.url
      DATABASE_URL         = local.database_url
    } : {},
  )

  env_evaluador = {
    AWS_REGION        = var.region
    BUCKET_EVALUACION = local.buckets.evaluacion
    BUCKET_MODELOS    = local.buckets.modelos
    DATABASE_URL      = local.database_url
  }

  envs = {
    backend   = local.env_backend
    worker    = local.env_worker
    evaluador = local.env_evaluador
  }
}

resource "aws_s3_object" "env" {
  for_each     = local.envs
  bucket       = aws_s3_bucket.b["deploy"].id
  key          = "config/${each.key}.env"
  content      = join("", [for k in sort(keys(each.value)) : "${k}=${each.value[k]}\n"])
  content_type = "text/plain"
}

# Lo que el sitio necesita saber de la infraestructura, en el bucket web al lado del index.html.
# El build del frontend no lleva ninguna dirección: la lee de acá al arrancar, así que
# desplegar.sh frontend no depende del estado de Terraform (y no borra este archivo).
resource "aws_s3_object" "config_web" {
  bucket        = aws_s3_bucket.b["web"].id
  key           = "config.json"
  content_type  = "application/json"
  cache_control = "no-cache"
  content = jsonencode({
    api = local.url_api
    cognito = {
      dominio   = local.cognito_dominio
      clienteId = aws_cognito_user_pool_client.web.id
      callback  = local.url_callback
      logout    = local.url_logout
    }
  })
}

locals {
  userdata_app = templatefile("${path.module}/plantillas/lt-app.sh.tftpl", {
    bucket_deploy = local.buckets.deploy
  })

  userdata_worker = templatefile("${path.module}/plantillas/lt-worker.sh.tftpl", {
    bucket_deploy = local.buckets.deploy
    fs_modelos    = aws_efs_file_system.modelos.id
  })

  userdata_eval = templatefile("${path.module}/plantillas/lt-eval.sh.tftpl", {
    bucket_deploy     = local.buckets.deploy
    bucket_evaluacion = local.buckets.evaluacion
    endpoint_rds      = aws_db_instance.ateneo.address
  })
}
