# Sección 08: cinco buckets con nombre de sufijo aleatorio (son únicos en todo AWS) y cifrado
# SSE-S3. Cuatro privados, con el acceso público bloqueado y los pedidos sin TLS denegados.
# El quinto, web, es el sitio estático: el paso 1 del login de la clase (cognito.tf).
# terraform destroy los vacía y los borra: la regla de uso es destruir al final de cada sesión.

resource "aws_s3_bucket" "b" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = true
  tags          = { Name = each.value, Rol = each.key }
}

# El cifrado en reposo, escrito y no heredado del valor por defecto de la cuenta. AWS cifra con
# SSE-S3 todo objeto nuevo desde enero de 2023, así que esto no cambia nada en ejecución: lo que
# cambia es que se ve en el plan y en la consola. La devolución de la E2 pidió que lo guardado en
# un bucket esté cifrado, y una afirmación así no puede quedar apoyada en un valor por defecto.
resource "aws_s3_bucket_server_side_encryption_configuration" "b" {
  for_each = aws_s3_bucket.b
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "b" {
  for_each           = aws_s3_bucket.b
  bucket             = each.value.id
  block_public_acls  = true
  ignore_public_acls = true
  # Sin ACL públicas en ninguno: el sitio se abre con su política, no con ACL.
  block_public_policy     = each.key != "web"
  restrict_public_buckets = each.key != "web"
}

# Un ONNX pisado se recupera.
resource "aws_s3_bucket_versioning" "modelos" {
  bucket = aws_s3_bucket.b["modelos"].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "estudios" {
  bucket = aws_s3_bucket.b["estudios"].id

  rule {
    id     = "borrar-7-dias"
    status = "Enabled"
    filter {}
    expiration {
      days = 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artefactos" {
  bucket = aws_s3_bucket.b["artefactos"].id

  rule {
    id     = "borrar-30-dias"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

# El navegador sube con un POST prefirmado. El origen es el sitio en S3, que no cambia: el CORS
# sale de acá y ya no hay que copiar ninguna dirección a mano.
resource "aws_s3_bucket_cors_configuration" "subidas" {
  for_each = toset(["estudios", "modelos"])
  bucket   = aws_s3_bucket.b[each.key].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST", "PUT", "GET", "HEAD"]
    allowed_origins = [local.url_sitio]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# --- Políticas ------------------------------------------------------------------------

locals {
  sin_tls = {
    for k in ["modelos", "estudios", "evaluacion", "artefactos"] : k => {
      Sid       = "SoloConTLS"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.b[k].arn, "${aws_s3_bucket.b[k].arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }
  }

  # bucket => lista de sentencias, ya en JSON
  politicas = {
    modelos    = jsonencode([local.sin_tls["modelos"]])
    estudios   = jsonencode([local.sin_tls["estudios"]])
    artefactos = jsonencode([local.sin_tls["artefactos"]])
    # El conjunto reservado solo se lee por el endpoint de la VPC, venga de quien venga. Deniega
    # leer, no escribir: el operador (o el constructor, con datos_demo) sube los casos.
    evaluacion = jsonencode([local.sin_tls["evaluacion"], {
      Sid       = "LeerSoloDesdeElEndpointDeLaVPC"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.b["evaluacion"].arn}/*"
      Condition = { StringNotEquals = { "aws:sourceVpce" = aws_vpc_endpoint.s3.id } }
    }])
    # El sitio se lee por el endpoint de sitio web de S3, que es HTTP: acá no va la regla de TLS.
    web = jsonencode([{
      Sid       = "SitioPublico"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.b["web"].arn}/*"
    }])
  }
}

resource "aws_s3_bucket_policy" "b" {
  for_each = local.politicas
  bucket   = aws_s3_bucket.b[each.key].id
  policy   = jsonencode({ Version = "2012-10-17", Statement = jsondecode(each.value) })

  depends_on = [aws_s3_bucket_public_access_block.b]
}

# --- El sitio: S3 como servidor web, por HTTP -----------------------------------------

resource "aws_s3_bucket_website_configuration" "web" {
  bucket = aws_s3_bucket.b["web"].id

  index_document {
    suffix = "index.html"
  }

  # /publicar y /consulta no son archivos: S3 contesta index.html y la app resuelve la ruta.
  error_document {
    key = "index.html"
  }
}

locals {
  url_sitio = "http://${aws_s3_bucket_website_configuration.web.website_endpoint}"
}

# Lo que el sitio necesita saber de la infraestructura, al lado del index.html. El build no lleva
# ninguna dirección: el constructor sube el sitio sin tocar este archivo.
resource "aws_s3_object" "config_web" {
  bucket        = aws_s3_bucket.b["web"].id
  key           = "config.json"
  content_type  = "application/json"
  cache_control = "no-cache"
  content = jsonencode({
    api = local.url_api
    cognito = {
      dominio  = local.cognito_dominio
      clientes = { for tipo, c in aws_cognito_user_pool_client.web : tipo => c.id }
      callback = local.url_callback
      logout   = local.url_logout
    }
  })
}
