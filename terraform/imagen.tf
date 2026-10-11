# Guía §8.2: la imagen dorada (Python 3.11, ONNX Runtime 1.18, numpy<2, agente de EFS y las dos
# unidades de systemd). Se construye una sola vez, solo si no se pasó ami_worker_id.
#
# El constructor nace en la subred app (tiene NAT para dnf y pip), corre el script, y si todo
# salió bien se apaga solo. Terraform espera ese apagado con la CLI de AWS (está en CloudShell)
# y recién entonces hace la AMI. El constructor queda detenido: cuesta centavos de disco y no
# conviene borrarlo, porque Terraform borraría la AMI con él. Si querés soltarlo, copiá el id de
# la AMI a ami_worker_id y después: terraform state rm 'aws_ami_from_instance.worker[0]'.

resource "aws_instance" "constructor" {
  count = var.ami_worker_id == "" ? 1 : 0

  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.tipo_worker
  subnet_id              = aws_subnet.capa["app-a"].id
  vpc_security_group_ids = [local.sg["app"]]
  iam_instance_profile   = data.aws_iam_instance_profile.lab.name
  user_data              = templatefile("${path.module}/plantillas/imagen-dorada.sh.tftpl", {})

  instance_initiated_shutdown_behavior = "stop"

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required"
  }

  tags = { Name = "tmp-build-worker" }

  lifecycle {
    ignore_changes = [ami, user_data]
  }

  depends_on = [aws_route.app_nat]
}

resource "terraform_data" "constructor_apagado" {
  count            = var.ami_worker_id == "" ? 1 : 0
  triggers_replace = [aws_instance.constructor[0].id]

  provisioner "local-exec" {
    # El waiter de la CLI espera 10 minutos; pip con onnxruntime puede tardar más: 3 vueltas.
    command = <<-EOT
      for i in 1 2 3; do
        aws ec2 wait instance-stopped --region ${var.region} --instance-ids ${aws_instance.constructor[0].id} && exit 0
      done
      echo "El constructor no se apagó. Mirá: aws ec2 get-console-output --latest --instance-id ${aws_instance.constructor[0].id}" >&2
      exit 1
    EOT
  }
}

resource "aws_ami_from_instance" "worker" {
  count              = var.ami_worker_id == "" ? 1 : 0
  name               = "ateneo-worker-${aws_instance.constructor[0].id}"
  source_instance_id = aws_instance.constructor[0].id
  tags               = { Name = "ateneo-worker" }

  depends_on = [terraform_data.constructor_apagado]
}
