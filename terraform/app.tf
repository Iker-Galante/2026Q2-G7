# Guía §07: target group, ALB externo y grupo de auto escalado del backend.

resource "aws_launch_template" "app" {
  name                   = "lt-app"
  image_id               = data.aws_ssm_parameter.al2023.value
  instance_type          = var.tipo_app
  vpc_security_group_ids = [local.sg["app"]]
  user_data              = base64encode(local.userdata_app)
  update_default_version = true

  iam_instance_profile {
    name = data.aws_iam_instance_profile.lab.name
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 20
      volume_type = "gp3"
      encrypted   = true
    }
  }

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "ateneo-app" }
  }

  # La AMI de AL2023 cambia sola cada tanto: no hace falta una versión nueva por eso.
  lifecycle {
    ignore_changes = [image_id]
  }
}

resource "aws_lb_target_group" "app" {
  name                 = "tg-app"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = aws_vpc.ateneo.id
  deregistration_delay = 60

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb" "app" {
  count              = var.encendido ? 1 : 0
  name               = "alb-ateneo"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [local.sg["alb"]]
  subnets            = local.sub_public
}

resource "aws_lb_listener" "app" {
  count             = var.encendido ? 1 : 0
  load_balancer_arn = aws_lb.app[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_autoscaling_group" "app" {
  name                      = "asg-app"
  vpc_zone_identifier       = local.sub_app
  target_group_arns         = [aws_lb_target_group.app.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 420

  # Sin desired_capacity: lo maneja la política de escalado. Apagado, max = 0 lo lleva a 0;
  # al prender, min lo sube solo.
  min_size = var.encendido ? var.app_min : 0
  max_size = var.encendido ? var.app_max : 0

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  # Sin instance_refresh: el lab lo deniega por SCP. Los cambios se aplican con
  # infra/refrescar.sh asg-app (guía §11).

  tag {
    key                 = "Name"
    value               = "ateneo-app"
    propagate_at_launch = true
  }

  # El .env, el NAT y la ruta tienen que existir antes de que la primera instancia arranque.
  depends_on = [aws_s3_object.env, aws_route.app_nat, aws_lb_listener.app]
}

resource "aws_autoscaling_policy" "app_cpu" {
  name                   = "cpu-60"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60
  }
}
