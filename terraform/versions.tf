terraform {
  # 1.10+ por el lock nativo del backend S3 (use_lockfile), sin DynamoDB.
  required_version = ">= 1.10"

  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
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
