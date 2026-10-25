# Sección 08: caché de modelos compartida entre workers, montada por Fargate. El evaluador no la
# monta: baja cada modelo una vez por evaluación y no comparte nada con otras capas.

resource "aws_efs_file_system" "modelos" {
  creation_token = "ateneo-modelos"
  encrypted      = true
  tags           = { Name = "fs-modelos" }
}

resource "aws_efs_backup_policy" "modelos" {
  file_system_id = aws_efs_file_system.modelos.id
  backup_policy {
    status = "DISABLED" # es una caché: lo que se pierde se vuelve a bajar de S3
  }
}

resource "aws_efs_mount_target" "modelos" {
  for_each        = toset(local.letras)
  file_system_id  = aws_efs_file_system.modelos.id
  subnet_id       = aws_subnet.capa["inferencia-${each.key}"].id
  security_groups = [local.sg["efs"]]
}
