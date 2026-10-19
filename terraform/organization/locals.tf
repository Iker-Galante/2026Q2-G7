data "aws_caller_identity" "yo" {}

# En el Learner Lab no se crean roles: tareas, Lambdas y constructor usan LabRole o su perfil de
# instancia (sección 09). En producción, cada servicio tendría el suyo.
data "aws_iam_role" "lab" {
  name = "LabRole"
}

data "aws_iam_instance_profile" "lab" {
  name = "LabInstanceProfile"
}

# Amazon Linux 2023, x86_64: la del constructor.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${var.region}.s3"
}

resource "random_string" "sufijo" {
  length  = 6
  upper   = false
  special = false
}

locals {
  sufijo = var.sufijo != "" ? var.sufijo : random_string.sufijo.result

  # El bucket web es el sitio, el paso 1 del login (cognito.tf); artefactos lleva el código que
  # construye el constructor (imagenes.tf).
  buckets = {
    web        = "ateneo-web-${local.sufijo}"
    modelos    = "ateneo-modelos-${local.sufijo}"
    estudios   = "ateneo-estudios-${local.sufijo}"
    evaluacion = "ateneo-evaluacion-${local.sufijo}"
    artefactos = "ateneo-artefactos-${local.sufijo}"
  }
}
