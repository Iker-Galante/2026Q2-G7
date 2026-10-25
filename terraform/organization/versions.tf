terraform {
  # 1.10+ por el lock nativo del backend S3 (use_lockfile), sin DynamoDB. El pipeline y tf.sh
  # fijan 1.16.5: Terraform se niega a leer un estado escrito por una versión más nueva que la
  # suya, así que la de CI no puede quedar atrás de la que use alguien en su máquina.
  required_version = ">= 1.10"

  required_providers {
    aws      = { source = "hashicorp/aws", version = "~> 6.0" }
    random   = { source = "hashicorp/random", version = "~> 3.6" }
    archive  = { source = "hashicorp/archive", version = "~> 2.4" }
    external = { source = "hashicorp/external", version = "~> 2.3" }
  }

  # El estado vive en un bucket propio, creado una sola vez con scripts/bootstrap-estado.sh.
  # Los valores van en backend.hcl (lo escribe ese script): terraform init -backend-config=backend.hcl
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Proyecto = "ateneo"
      Gestion  = "terraform"
    }
  }
}
