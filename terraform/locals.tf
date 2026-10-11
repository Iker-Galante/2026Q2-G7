data "aws_caller_identity" "yo" {}

# En el Learner Lab no se crean roles: todo usa LabRole y su perfil de instancia.
data "aws_iam_role" "lab" {
  name = "LabRole"
}

data "aws_iam_instance_profile" "lab" {
  name = "LabInstanceProfile"
}

# Amazon Linux 2023, x86_64: la de lt-app y la base de la imagen dorada.
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "random_string" "sufijo" {
  length  = 6
  upper   = false
  special = false
}

locals {
  sufijo = var.sufijo != "" ? var.sufijo : random_string.sufijo.result
  sqs    = var.modo_inferencia == "sqs"
  http   = var.modo_inferencia == "http"

  buckets = {
    deploy     = "ateneo-deploy-${local.sufijo}"
    web        = "ateneo-web-${local.sufijo}"
    modelos    = "ateneo-modelos-${local.sufijo}"
    estudios   = "ateneo-estudios-${local.sufijo}"
    evaluacion = "ateneo-evaluacion-${local.sufijo}"
  }

  ami_worker = var.ami_worker_id != "" ? var.ami_worker_id : one(aws_ami_from_instance.worker[*].id)
}
