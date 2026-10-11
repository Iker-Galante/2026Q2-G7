# Guía §03. Terraform borra la regla de salida por defecto de cada grupo que crea, así que
# la salida libre se declara explícita donde corresponde, y sg-eval y sg-worker quedan apretados.
# Ningún puerto 22 en toda la arquitectura: el acceso administrativo es por Session Manager.

locals {
  grupos = {
    alb     = "ALB externo"
    app     = "Instancias del backend"
    alb-int = "ALB interno (modo http)"
    worker  = "Workers de inferencia"
    data    = "RDS"
    eval    = "Instancia de evaluación: nadie inicia conexiones hacia ella"
    efs     = "Mount targets de EFS"
  }
}

resource "aws_security_group" "g" {
  for_each    = local.grupos
  name        = "ateneo-${each.key}" # AWS no deja que el nombre empiece con "sg-"; la etiqueta sí
  description = each.value
  vpc_id      = aws_vpc.ateneo.id
  tags        = { Name = "sg-${each.key}" }
}

resource "aws_security_group" "vpce" {
  name        = "ateneo-vpce"
  description = "Endpoints de interfaz (SQS)"
  vpc_id      = aws_vpc.ateneo.id
  tags        = { Name = "sg-vpce" }
}

data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${var.region}.s3"
}

locals {
  sg = { for k, g in aws_security_group.g : k => g.id }

  # [grupo, puerto, origen (sg) o null para 0.0.0.0/0, descripción]
  entradas = {
    alb-http         = ["alb", 80, null, "HTTP desde internet"]
    app-desde-alb    = ["app", 8080, "alb", "backend desde el ALB"]
    albint-desde-app = ["alb-int", 8081, "app", "ALB interno desde el backend"]
    worker-desde-alb = ["worker", 8081, "alb-int", "worker desde el ALB interno"]
    data-desde-app   = ["data", 5432, "app", "PostgreSQL desde app"]
    data-desde-wrk   = ["data", 5432, "worker", "PostgreSQL desde worker"]
    data-desde-eval  = ["data", 5432, "eval", "PostgreSQL desde eval"]
    efs-desde-wrk    = ["efs", 2049, "worker", "NFS desde worker"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "r" {
  for_each = local.entradas

  security_group_id            = local.sg[each.value[0]]
  ip_protocol                  = "tcp"
  from_port                    = each.value[1]
  to_port                      = each.value[1]
  referenced_security_group_id = each.value[2] == null ? null : local.sg[each.value[2]]
  cidr_ipv4                    = each.value[2] == null ? "0.0.0.0/0" : null
  description                  = each.value[3]
}

resource "aws_vpc_security_group_ingress_rule" "vpce" {
  for_each = toset(["app", "worker"])

  security_group_id            = aws_security_group.vpce.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = local.sg[each.key]
  description                  = "HTTPS a los endpoints desde ${each.key}"
}

# Salida libre: la que AWS pone por defecto, ahora escrita.
resource "aws_vpc_security_group_egress_rule" "todo" {
  for_each = toset(["alb", "app", "alb-int", "data", "efs"])

  security_group_id = local.sg[each.key]
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "salida libre (valor por defecto)"
}

# sg-eval y sg-worker: solo lo que necesitan (§03).
resource "aws_vpc_security_group_egress_rule" "s3" {
  for_each = toset(["eval", "worker"])

  security_group_id = local.sg[each.key]
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  prefix_list_id    = data.aws_ec2_managed_prefix_list.s3.id
  description       = "HTTPS a S3 por el endpoint"
}

resource "aws_vpc_security_group_egress_rule" "base" {
  for_each = toset(["eval", "worker"])

  security_group_id            = local.sg[each.key]
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  referenced_security_group_id = local.sg["data"]
  description                  = "PostgreSQL"
}

resource "aws_vpc_security_group_egress_rule" "worker_efs" {
  security_group_id            = local.sg["worker"]
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
  referenced_security_group_id = local.sg["efs"]
  description                  = "NFS a EFS"
}

# Modo sqs: el worker consume la cola por el endpoint de interfaz.
resource "aws_vpc_security_group_egress_rule" "worker_sqs" {
  security_group_id            = local.sg["worker"]
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.vpce.id
  description                  = "HTTPS al endpoint de SQS"
}
