# Decisión 06: las imágenes se construyen dentro de la cuenta. terraform apply empaqueta el
# código del repositorio, lo sube a S3 y lanza una instancia que construye las dos imágenes, las
# sube a ECR con el hash del código como etiqueta, sube el sitio al bucket web y se apaga. Quien
# corre Terraform no necesita Docker. Si el código no cambió, el hash es el mismo y el plan no
# muestra cambios.

resource "aws_ecr_repository" "r" {
  for_each             = toset(["backend", "ml"])
  name                 = "ateneo/${each.key}"
  image_tag_mutability = "IMMUTABLE" # una etiqueta es una versión del código, para siempre
  force_delete         = true        # terraform destroy borra también las imágenes
}

resource "aws_ecr_lifecycle_policy" "r" {
  for_each   = aws_ecr_repository.r
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar las últimas cinco imágenes"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

# --- El código: qué entra en las imágenes y su hash -----------------------------------

locals {
  raiz = abspath("${path.module}/../..")

  # Lo que leen los Dockerfiles, y nada más (ni tmp/, ni node_modules, ni el estado).
  carpetas_codigo = ["backend/app", "worker", "evaluador", "ateneo_ml", "migraciones", "tools", "docker", "frontend/src"]
  codigo = sort([
    for f in distinct(concat(
      flatten([for c in local.carpetas_codigo : [for f in fileset("${local.raiz}/${c}", "**") : "${c}/${f}"]]),
      ["backend/requirements.txt", "frontend/index.html"],
      [for f in fileset("${local.raiz}/frontend", "*.{json,ts}") : "frontend/${f}"],
    )) : f if !strcontains(f, "__pycache__") && !endswith(f, ".pyc")
  ])

  # La etiqueta de las dos imágenes. Cambia si cambia cualquier archivo de la lista.
  version_codigo = substr(sha256(join("\n", [for f in local.codigo : "${f} ${filesha256("${local.raiz}/${f}")}"])), 0, 16)

  registro = split("/", aws_ecr_repository.r["backend"].repository_url)[0]
  imagen = {
    for k, r in aws_ecr_repository.r : k => "${r.repository_url}:${local.version_codigo}"
  }
}

data "archive_file" "codigo" {
  type        = "zip"
  output_path = "${path.module}/.build/codigo-${local.version_codigo}.zip"

  dynamic "source" {
    for_each = local.codigo
    content {
      content  = file("${local.raiz}/${source.value}")
      filename = source.value
    }
  }
}

resource "aws_s3_object" "codigo" {
  bucket = local.buckets.artefactos
  key    = "codigo/${local.version_codigo}.zip"
  source = data.archive_file.codigo.output_path
  # Sin etag a propósito: la clave ya lleva el hash del código.

  depends_on = [terraform_data.buckets]
}

# --- El constructor -------------------------------------------------------------------

# Una t3.large en la capa de aplicación, porque necesita internet para bajar dependencias. Al
# terminar se apaga sola y queda detenida, sin costo de cómputo, hasta que el código cambie y
# Terraform la reemplace (el user data lleva la versión).
resource "aws_instance" "constructor" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = "t3.large"
  subnet_id              = aws_subnet.capa["aplicacion-a"].id
  vpc_security_group_ids = [local.sg["constructor"]]
  iam_instance_profile   = data.aws_iam_instance_profile.lab.name

  user_data = templatefile("${path.module}/plantillas/constructor.sh.tftpl", {
    region            = var.region
    version           = local.version_codigo
    registro          = local.registro
    bucket_artefactos = local.buckets.artefactos
    clave_codigo      = aws_s3_object.codigo.key
    bucket_web        = local.buckets.web
    bucket_modelos    = local.buckets.modelos
    bucket_evaluacion = local.buckets.evaluacion
    datos_demo        = var.datos_demo
  })
  user_data_replace_on_change = true

  instance_initiated_shutdown_behavior = "stop"

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  tags = { Name = "ateneo-constructor" }

  lifecycle {
    ignore_changes = [ami] # la AMI de AL2023 cambia sola cada tanto: no es motivo para reconstruir
  }

  depends_on = [
    aws_route.aplicacion_nat,
    aws_route_table_association.capa,
    module.endpoints,
    aws_vpc_security_group_egress_rule.r,
    aws_s3_bucket_policy.b,
  ]
}

# Los servicios de ECS se crean recién cuando las dos imágenes están en ECR. Si el constructor se
# apaga sin haberlas subido, el apply falla y dice dónde está el log (riesgo 02).
resource "terraform_data" "imagenes" {
  count            = var.esperar_imagenes ? 1 : 0
  triggers_replace = [local.version_codigo, aws_instance.constructor.id]

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      hay() { aws ecr describe-images --region ${var.region} --repository-name "ateneo/$1" --image-ids imageTag=${local.version_codigo} >/dev/null 2>&1; }
      echo "esperando las imágenes ${local.version_codigo} (unos diez minutos la primera vez)…"
      for i in $(seq 1 90); do
        if hay backend && hay ml; then echo "imágenes listas"; exit 0; fi
        estado=$(aws ec2 describe-instances --region ${var.region} --instance-ids ${aws_instance.constructor.id} --query 'Reservations[0].Instances[0].State.Name' --output text)
        if [ "$estado" = "stopped" ] && ! { hay backend && hay ml; }; then
          echo "El constructor se apagó sin subir las imágenes. Log: aws s3 cp s3://${local.buckets.artefactos}/logs/constructor-${local.version_codigo}.log -" >&2
          exit 1
        fi
        sleep 20
      done
      echo "Pasaron 30 minutos. Log: aws ec2 get-console-output --latest --region ${var.region} --instance-id ${aws_instance.constructor.id}" >&2
      exit 1
    EOT
  }
}
