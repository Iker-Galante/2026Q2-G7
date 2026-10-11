# Guía §8.1: caché compartida de modelos para los workers. Solo se monta desde sg-worker.

resource "aws_efs_file_system" "modelos" {
  creation_token = "fs-modelos"
  encrypted      = true
  tags           = { Name = "fs-modelos" }
}

resource "aws_efs_backup_policy" "modelos" {
  file_system_id = aws_efs_file_system.modelos.id
  backup_policy {
    status = "DISABLED"
  }
}

resource "aws_efs_mount_target" "modelos" {
  for_each        = toset(["a", "b"])
  file_system_id  = aws_efs_file_system.modelos.id
  subnet_id       = aws_subnet.capa["inf-${each.key}"].id
  security_groups = [local.sg["efs"]]
}
