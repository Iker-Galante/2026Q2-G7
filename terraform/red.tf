# Guía §02: VPC 10.0.0.0/16, siete subredes en cuatro capas y una de evaluación.

resource "aws_vpc" "ateneo" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "ateneo" }
}

resource "aws_internet_gateway" "ateneo" {
  vpc_id = aws_vpc.ateneo.id
  tags   = { Name = "ateneo-igw" }
}

locals {
  # capa => [cidr zona a, cidr zona b]
  subredes = {
    public = ["10.0.0.0/24", "10.0.1.0/24"]
    app    = ["10.0.10.0/24", "10.0.11.0/24"]
    data   = ["10.0.20.0/24", "10.0.21.0/24"]
    inf    = ["10.0.30.0/24", "10.0.31.0/24"]
  }
  letras = ["a", "b"]

  subredes_planas = merge([
    for capa, cidrs in local.subredes : {
      for i, cidr in cidrs : "${capa}-${local.letras[i]}" => { capa = capa, cidr = cidr, zona = var.zonas[i] }
    }
  ]...)
}

resource "aws_subnet" "capa" {
  for_each = local.subredes_planas

  vpc_id            = aws_vpc.ateneo.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.zona
  tags              = { Name = "ateneo-${each.key}", Capa = each.value.capa }
}

# Una sola, en la zona «a»: un trabajo por lotes que falla se relanza (§9.1).
resource "aws_subnet" "eval" {
  vpc_id            = aws_vpc.ateneo.id
  cidr_block        = "10.0.40.0/24"
  availability_zone = var.zonas[0]
  tags              = { Name = "ateneo-eval", Capa = "eval" }
}

locals {
  sub_public = [aws_subnet.capa["public-a"].id, aws_subnet.capa["public-b"].id]
  sub_app    = [aws_subnet.capa["app-a"].id, aws_subnet.capa["app-b"].id]
  sub_data   = [aws_subnet.capa["data-a"].id, aws_subnet.capa["data-b"].id]
  sub_inf    = [aws_subnet.capa["inf-a"].id, aws_subnet.capa["inf-b"].id]
}

# --- Tablas de ruteo -----------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.ateneo.id
  tags   = { Name = "rtb-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.ateneo.id
}

resource "aws_route_table_association" "public" {
  for_each       = toset(["a", "b"])
  subnet_id      = aws_subnet.capa["public-${each.key}"].id
  route_table_id = aws_route_table.public.id
}

# Dos tablas de aplicación, como deja el asistente (§2.1): la ruta al NAT va en las dos.
resource "aws_route_table" "app" {
  for_each = toset(["a", "b"])
  vpc_id   = aws_vpc.ateneo.id
  tags     = { Name = "rtb-app-${each.key}" }
}

resource "aws_route_table_association" "app" {
  for_each       = toset(["a", "b"])
  subnet_id      = aws_subnet.capa["app-${each.key}"].id
  route_table_id = aws_route_table.app[each.key].id
}

# Tres tablas sin salida (§2.3): la única ruta es 10.0.0.0/16 local (más el endpoint de S3).
resource "aws_route_table" "cerrada" {
  for_each = toset(["inf", "data", "eval"])
  vpc_id   = aws_vpc.ateneo.id
  tags     = { Name = "rtb-${each.key}" }
}

resource "aws_route_table_association" "inf" {
  for_each       = toset(["a", "b"])
  subnet_id      = aws_subnet.capa["inf-${each.key}"].id
  route_table_id = aws_route_table.cerrada["inf"].id
}

resource "aws_route_table_association" "data" {
  for_each       = toset(["a", "b"])
  subnet_id      = aws_subnet.capa["data-${each.key}"].id
  route_table_id = aws_route_table.cerrada["data"].id
}

resource "aws_route_table_association" "eval" {
  subnet_id      = aws_subnet.eval.id
  route_table_id = aws_route_table.cerrada["eval"].id
}

# --- NAT: lo más caro que queda prendido. Existe solo con encendido = true. -----------

resource "aws_eip" "nat" {
  count  = var.encendido ? 1 : 0
  domain = "vpc"
  tags   = { Name = "ateneo-nat" }
}

resource "aws_nat_gateway" "ateneo" {
  count         = var.encendido ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.capa["public-a"].id
  tags          = { Name = "ateneo-nat" }

  depends_on = [aws_internet_gateway.ateneo]
}

resource "aws_route" "app_nat" {
  for_each               = var.encendido ? toset(["a", "b"]) : toset([])
  route_table_id         = aws_route_table.app[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.ateneo[0].id
}

# --- Endpoints ------------------------------------------------------------------------

# Gateway de S3: gratis, y el único camino a S3 de inferencia y evaluación.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.ateneo.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids = concat(
    [for k in ["a", "b"] : aws_route_table.app[k].id],
    [for k in ["inf", "data", "eval"] : aws_route_table.cerrada[k].id],
  )
  tags = { Name = "ateneo-s3" }
}

# Interfaz de SQS (modo sqs): los workers no tienen internet y tienen que llegar a la cola.
# Con private DNS, sqs.us-east-1.amazonaws.com resuelve a estas IPs en toda la VPC, así
# que la capa app también lo usa (y deja de pasar por el NAT para encolar).
# Cuesta lo mismo que el ALB interno que reemplaza (~USD 0,01/h por zona).
resource "aws_vpc_endpoint" "sqs" {
  count               = var.encendido && local.sqs ? 1 : 0
  vpc_id              = aws_vpc.ateneo.id
  service_name        = "com.amazonaws.${var.region}.sqs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.sub_inf
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "ateneo-sqs" }
}

# --- NACL de evaluación (§9.4): la segunda barrera, sin estado ------------------------

resource "aws_network_acl" "eval" {
  vpc_id     = aws_vpc.ateneo.id
  subnet_ids = [aws_subnet.eval.id]
  tags       = { Name = "nacl-eval" }

  # Salida: leer S3 por el endpoint y escribir la certificación en la base.
  egress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }
  egress {
    rule_no    = 200
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "10.0.20.0/23"
    from_port  = 5432
    to_port    = 5432
  }

  # Entrada: solo las respuestas, por puertos efímeros. Nadie inicia hacia eval-1.
  ingress {
    rule_no    = 100
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }
  ingress {
    rule_no    = 200
    protocol   = "tcp"
    action     = "allow"
    cidr_block = "10.0.20.0/23"
    from_port  = 1024
    to_port    = 65535
  }
}
