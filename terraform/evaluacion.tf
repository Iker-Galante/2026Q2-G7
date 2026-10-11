# Guía §09: eval-1, una instancia suelta (sin ASG) en la subred aislada.

resource "aws_launch_template" "eval" {
  name                   = "lt-eval"
  image_id               = local.ami_worker
  instance_type          = var.tipo_eval
  user_data              = base64encode(local.userdata_eval)
  update_default_version = true

  iam_instance_profile {
    name = data.aws_iam_instance_profile.lab.name
  }

  # Subred y grupo van juntos en la interfaz (§9.1): así run-instances no pide nada más.
  network_interfaces {
    subnet_id                   = aws_subnet.eval.id
    security_groups             = [local.sg["eval"]]
    associate_public_ip_address = false
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 30
      volume_type = "gp3"
      encrypted   = true
    }
  }

  metadata_options {
    http_tokens = "required"
  }

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "eval-1" }
  }

  tag_specifications {
    resource_type = "volume"
    tags          = { Name = "eval-1" }
  }
}

# Cada versión nueva de la plantilla (otro user data, otra AMI) reemplaza la instancia:
# el user data corre una sola vez por instancia, así que relanzar es la forma de aplicar.
# Para tomar un worker-latest.zip nuevo sin cambiar nada acá:
#   terraform apply -replace=aws_instance.eval[0]
resource "aws_instance" "eval" {
  count = var.encendido && var.evaluador_activo ? 1 : 0

  launch_template {
    id      = aws_launch_template.eval.id
    version = aws_launch_template.eval.latest_version
  }

  # Una instancia detenida sigue pagando su disco y arranca con el boletín viejo (§9.5).
  instance_initiated_shutdown_behavior = "terminate"

  depends_on = [
    aws_s3_object.env,
    aws_network_acl.eval,
    aws_vpc_security_group_egress_rule.s3,
    aws_vpc_security_group_egress_rule.base,
    aws_s3_bucket_policy.evaluacion,
    aws_rds_instance_state.ateneo,
  ]
}
