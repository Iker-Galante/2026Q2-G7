# Guía §05: PostgreSQL 16, db.t3.micro, single-AZ, en las subredes de datos.

resource "aws_db_subnet_group" "ateneo" {
  name       = "ateneo-data"
  subnet_ids = local.sub_data
  tags       = { Name = "ateneo-data" }
}

# Sin / @ " ni espacios (RDS no los acepta); el resto se codifica al armar la URL.
resource "random_password" "db" {
  length           = 24
  special          = true
  override_special = "!#%*-_=+"
}

resource "aws_db_instance" "ateneo" {
  identifier     = "ateneo-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 0
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "ateneo"
  username = "ateneo"
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.ateneo.name
  vpc_security_group_ids = [local.sg["data"]]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period = 7
  deletion_protection     = false
  skip_final_snapshot     = true
  apply_immediately       = true

  tags = { Name = "ateneo-db" }
}

# El interruptor también detiene la base. Ojo: AWS la vuelve a prender sola a los 7 días;
# el guardián (guardian.tf) la detiene de nuevo esa noche.
resource "aws_rds_instance_state" "ateneo" {
  identifier = aws_db_instance.ateneo.identifier
  state      = var.encendido ? "available" : "stopped"
}

locals {
  database_url = "postgresql://ateneo:${urlencode(random_password.db.result)}@${aws_db_instance.ateneo.address}:5432/ateneo"
}
