# Guía §08: workers de inferencia con la imagen dorada.
#   modo http: ALB interno → tg-inf → asg-inf (como hoy).
#   modo sqs:  sin ALB interno; los workers consumen ateneo-inferencias y el grupo escala
#              por mensajes en cola por instancia, además de por CPU.

resource "aws_launch_template" "worker" {
  name                   = "lt-worker"
  image_id               = local.ami_worker
  instance_type          = var.tipo_worker
  vpc_security_group_ids = [local.sg["worker"]]
  user_data              = base64encode(local.userdata_worker)
  update_default_version = true

  iam_instance_profile {
    name = data.aws_iam_instance_profile.lab.name
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
    tags          = { Name = "ateneo-worker" }
  }
}

resource "aws_lb_target_group" "inf" {
  count                = local.http ? 1 : 0
  name                 = "tg-inf"
  port                 = 8081
  protocol             = "HTTP"
  vpc_id               = aws_vpc.ateneo.id
  deregistration_delay = 60

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb" "inf" {
  count              = var.encendido && local.http ? 1 : 0
  name               = "alb-ateneo-int"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [local.sg["alb-int"]]
  subnets            = local.sub_inf
}

resource "aws_lb_listener" "inf" {
  count             = var.encendido && local.http ? 1 : 0
  load_balancer_arn = aws_lb.inf[0].arn
  port              = 8081
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.inf[0].arn
  }
}

resource "aws_autoscaling_group" "inf" {
  name                = "asg-inf"
  vpc_zone_identifier = local.sub_inf
  target_group_arns   = local.http ? [aws_lb_target_group.inf[0].arn] : []

  # Sin balanceador no hay health check de ELB: el grupo mira el estado de la instancia, y
  # un worker que no consume se ve en la alarma de cola atascada (notificaciones.tf).
  health_check_type         = local.http ? "ELB" : "EC2"
  health_check_grace_period = 180

  min_size = var.encendido ? var.inf_min : 0
  max_size = var.encendido ? var.inf_max : 0

  # Hace falta para la métrica de instancias en servicio del escalado por cola.
  enabled_metrics = ["GroupInServiceInstances"]

  launch_template {
    id      = aws_launch_template.worker.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "ateneo-worker"
    propagate_at_launch = true
  }

  depends_on = [aws_s3_object.env, aws_efs_mount_target.modelos, aws_vpc_endpoint.sqs]
}

resource "aws_autoscaling_policy" "inf_cpu" {
  name                   = "cpu-70"
  autoscaling_group_name = aws_autoscaling_group.inf.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 70
  }
}

# Mensajes visibles / instancias en servicio: la receta de AWS para escalar consumidores de SQS.
resource "aws_autoscaling_policy" "inf_cola" {
  count                  = local.sqs ? 1 : 0
  name                   = "mensajes-por-instancia"
  autoscaling_group_name = aws_autoscaling_group.inf.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    target_value = var.mensajes_por_worker

    customized_metric_specification {
      metrics {
        id          = "m1"
        return_data = false
        metric_stat {
          stat = "Sum"
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = aws_sqs_queue.inferencias.name
            }
          }
        }
      }
      metrics {
        id          = "m2"
        return_data = false
        metric_stat {
          stat = "Average"
          metric {
            namespace   = "AWS/AutoScaling"
            metric_name = "GroupInServiceInstances"
            dimensions {
              name  = "AutoScalingGroupName"
              value = aws_autoscaling_group.inf.name
            }
          }
        }
      }
      metrics {
        id          = "e1"
        label       = "mensajes por instancia"
        expression  = "m1 / m2"
        return_data = true
      }
    }
  }
}
