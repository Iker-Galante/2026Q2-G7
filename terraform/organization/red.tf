# Sección 06: VPC 10.0.0.0/16, once subredes en seis capas ordenadas por sensibilidad, una tabla
# de ruteo por capa. Ninguna pieza tiene IP pública: la única entrada es API Gateway por el VPC
# Link y la única salida, el NAT de la capa de aplicación.

resource "aws_vpc" "ateneo" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true # los endpoints de interfaz con DNS privado lo necesitan
  tags                 = { Name = "ateneo" }
}

resource "aws_internet_gateway" "ateneo" {
  vpc_id = aws_vpc.ateneo.id
  tags   = { Name = "ateneo-igw" }
}

locals {
  # capa => [cidr zona a, cidr zona b]. Evaluación tiene una sola: no necesita alta disponibilidad.
  subredes = {
    publica    = ["10.0.0.0/24", "10.0.1.0/24"]   # el NAT
    aplicacion = ["10.0.10.0/24", "10.0.11.0/24"] # VPC Link, ALB interno, api, procesador, constructor
    datos      = ["10.0.20.0/24", "10.0.21.0/24"] # RDS
    inferencia = ["10.0.30.0/24", "10.0.31.0/24"] # worker, puntos de montaje de EFS
    evaluacion = ["10.0.40.0/24"]                 # evaluador, detrás de la NACL
    endpoints  = ["10.0.50.0/24", "10.0.51.0/24"] # endpoints de interfaz de ECR, Logs y SQS
  }
  letras = ["a", "b"]

  subredes_planas = merge([
    for capa, cidrs in local.subredes : {
      for i, cidr in cidrs : "${capa}-${local.letras[i]}" => { capa = capa, cidr = cidr, zona = var.zonas[i] }
    }
  ]...)

  # capa => ids de sus subredes, en orden de zona
  sub = { for capa, cidrs in local.subredes : capa => [for i, _ in cidrs : aws_subnet.capa["${capa}-${local.letras[i]}"].id] }
}

resource "aws_subnet" "capa" {
  for_each = local.subredes_planas

  vpc_id            = aws_vpc.ateneo.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.zona
  tags              = { Name = "ateneo-${each.key}", Capa = each.value.capa }
}

# --- Tablas de ruteo: una por capa, generadas por código --------------------------------

resource "aws_route_table" "capa" {
  for_each = local.subredes
  vpc_id   = aws_vpc.ateneo.id
  tags     = { Name = "rtb-${each.key}" }
}

resource "aws_route_table_association" "capa" {
  for_each       = local.subredes_planas
  subnet_id      = aws_subnet.capa[each.key].id
  route_table_id = aws_route_table.capa[each.value.capa].id
}

resource "aws_route" "publica_internet" {
  route_table_id         = aws_route_table.capa["publica"].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.ateneo.id
}

# Un solo NAT, y solo la capa de aplicación sale por él (riesgo 03).
resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "ateneo-nat" }
}

resource "aws_nat_gateway" "ateneo" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.capa["publica-a"].id
  tags          = { Name = "ateneo-nat" }

  depends_on = [aws_internet_gateway.ateneo]
}

resource "aws_route" "aplicacion_nat" {
  route_table_id         = aws_route_table.capa["aplicacion"].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.ateneo.id
}

# --- Endpoints ------------------------------------------------------------------------

# Gateway de S3: gratis. Datos no lo tiene: RDS no usa S3, y lo que una capa no necesita no lo tiene.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.ateneo.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [for capa in ["aplicacion", "inferencia", "evaluacion"] : aws_route_table.capa[capa].id]
  tags              = { Name = "ateneo-s3" }
}

# Fargate sin internet necesita bajar imágenes (ECR) y escribir logs; worker y evaluador, además,
# SQS. Con DNS privado, los nombres públicos de estos servicios resuelven a estas IPs en toda la
# VPC. Van en subredes propias para no entrar a la subred aislada ni atravesar su NACL (decisión 07).
resource "aws_vpc_endpoint" "interfaz" {
  for_each = toset(["ecr.api", "ecr.dkr", "logs", "sqs"])

  vpc_id              = aws_vpc.ateneo.id
  service_name        = "com.amazonaws.${var.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.sub["endpoints"]
  security_group_ids  = [aws_security_group.g["endpoints"].id]
  private_dns_enabled = true
  tags                = { Name = "ateneo-${replace(each.key, ".", "-")}" }
}

# --- NACL de evaluación: la segunda barrera, sin estado --------------------------------

# Entrada: solo respuestas, por puertos efímeros. Salida: solo 443, que sin ruta a internet llega
# únicamente a S3 y a los endpoints. Ni el DNS de la VPC ni los metadatos de la tarea pasan por
# una NACL, así que no hace falta abrirlos.
resource "aws_network_acl" "evaluacion" {
  vpc_id     = aws_vpc.ateneo.id
  subnet_ids = local.sub["evaluacion"]
  tags       = { Name = "nacl-evaluacion" }

  egress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  ingress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }
}
