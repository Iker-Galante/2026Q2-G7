# Sección 09, red: grupos de seguridad encadenados por referencia. Terraform borra la salida libre
# que AWS pone por defecto, así que cada grupo tiene solo lo que está escrito acá. procesador,
# worker, evaluador y constructor no tienen ninguna regla de entrada.

locals {
  grupos = {
    vpclink     = "VPC Link de API Gateway"
    alb         = "ALB interno"
    api         = "Tareas de la api"
    procesador  = "Tareas del procesador: sin entrada"
    worker      = "Tareas del worker: sin entrada"
    evaluador   = "Tarea del evaluador: sin entrada"
    endpoints   = "Endpoints de interfaz (ECR, Logs, SQS)"
    db          = "RDS"
    efs         = "Puntos de montaje de EFS"
    constructor = "Instancia que construye las imagenes: sin entrada"
  }

  sg = { for k, g in aws_security_group.g : k => g.id }

  # nombre => [grupo, puerto, origen]
  entradas = merge(
    {
      alb-desde-vpclink   = ["alb", 80, "vpclink"]
      api-desde-alb       = ["api", 8080, "alb"]
      db-desde-api        = ["db", 5432, "api"]
      db-desde-procesador = ["db", 5432, "procesador"]
      efs-desde-worker    = ["efs", 2049, "worker"]
    },
    { for g in ["api", "procesador", "worker", "evaluador", "constructor"] : "endpoints-desde-${g}" => ["endpoints", 443, g] },
  )

  # nombre => [grupo, puerto, destino]: otro grupo, "internet" (por el NAT o los endpoints) o "s3"
  salidas = {
    vpclink-a-alb          = ["vpclink", 80, "alb"]
    alb-a-api              = ["alb", 8080, "api"]
    api-a-db               = ["api", 5432, "db"]
    api-a-internet         = ["api", 443, "internet"]
    procesador-a-db        = ["procesador", 5432, "db"]
    procesador-a-internet  = ["procesador", 443, "internet"]
    worker-a-endpoints     = ["worker", 443, "endpoints"]
    worker-a-s3            = ["worker", 443, "s3"]
    worker-a-efs           = ["worker", 2049, "efs"]
    evaluador-a-endpoints  = ["evaluador", 443, "endpoints"]
    evaluador-a-s3         = ["evaluador", 443, "s3"]
    constructor-a-internet = ["constructor", 443, "internet"]
  }
}

resource "aws_security_group" "g" {
  for_each    = local.grupos
  name        = "ateneo-${each.key}" # AWS no deja que el nombre empiece con "sg-"; la etiqueta sí
  description = each.value
  vpc_id      = aws_vpc.ateneo.id
  tags        = { Name = "sg-${each.key}" }
}

resource "aws_vpc_security_group_ingress_rule" "r" {
  for_each = local.entradas

  security_group_id            = local.sg[each.value[0]]
  ip_protocol                  = "tcp"
  from_port                    = each.value[1]
  to_port                      = each.value[1]
  referenced_security_group_id = local.sg[each.value[2]]
  description                  = each.key
}

resource "aws_vpc_security_group_egress_rule" "r" {
  for_each = local.salidas

  security_group_id            = local.sg[each.value[0]]
  ip_protocol                  = "tcp"
  from_port                    = each.value[1]
  to_port                      = each.value[1]
  referenced_security_group_id = contains(["internet", "s3"], each.value[2]) ? null : local.sg[each.value[2]]
  cidr_ipv4                    = each.value[2] == "internet" ? "0.0.0.0/0" : null
  prefix_list_id               = each.value[2] == "s3" ? data.aws_ec2_managed_prefix_list.s3.id : null
  description                  = each.key
}
