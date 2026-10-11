# Guía §04: cinco buckets privados, cifrados (SSE-S3 por defecto) y con el acceso público bloqueado.

resource "aws_s3_bucket" "b" {
  for_each      = local.buckets
  bucket        = each.value
  force_destroy = var.permitir_borrar_buckets
  tags          = { Name = each.value, Rol = each.key }
}

resource "aws_s3_bucket_public_access_block" "b" {
  for_each                = aws_s3_bucket.b
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versionado en modelos (un ONNX pisado se recupera) y en deploy (volver a un zip anterior).
resource "aws_s3_bucket_versioning" "b" {
  for_each = toset(["modelos", "deploy"])
  bucket   = aws_s3_bucket.b[each.key].id
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

resource "aws_s3_bucket_lifecycle_configuration" "deploy" {
  bucket = aws_s3_bucket.b["deploy"].id

  rule {
    id     = "zips-viejos-30-dias"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# El navegador sube con un POST prefirmado: sin POST en la lista, S3 contesta sin la
# cabecera y la pantalla dice «no se pudo subir» sin rastro en ningún log (§04).
# El origen es el DNS del ALB externo; cuando el sistema está apagado no hay ALB y queda "*".
resource "aws_s3_bucket_cors_configuration" "subidas" {
  for_each = toset(["estudios", "modelos"])
  bucket   = aws_s3_bucket.b[each.key].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST", "PUT", "GET", "HEAD"]
    allowed_origins = var.encendido ? ["http://${aws_lb.app[0].dns_name}"] : ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Deniega leer el conjunto reservado salvo desde el endpoint de la VPC. Deniega leer, no
# escribir: subir casos nuevos se controla por identidad (§04).
resource "aws_s3_bucket_policy" "evaluacion" {
  bucket = aws_s3_bucket.b["evaluacion"].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "LeerSoloDesdeElEndpointDeLaVPC"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.b["evaluacion"].arn}/*"
      Condition = { StringNotEquals = { "aws:sourceVpce" = aws_vpc_endpoint.s3.id } }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.b]
}
