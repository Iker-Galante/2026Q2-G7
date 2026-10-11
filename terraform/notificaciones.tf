# SNS: un tema de alertas. Lo alimentan las alarmas de CloudWatch y el informe del guardián.

resource "aws_sns_topic" "alertas" {
  name = "ateneo-alertas"
}

resource "aws_sns_topic_subscription" "mail" {
  count     = var.email_alertas != "" ? 1 : 0
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.email_alertas # AWS manda un mail de confirmación: hay que aceptarlo
}

locals {
  alarma_comun = {
    alarm_actions      = [aws_sns_topic.alertas.arn]
    ok_actions         = [aws_sns_topic.alertas.arn]
    treat_missing_data = "notBreaching"
  }
}

# Un trabajo agotó sus 3 intentos.
resource "aws_cloudwatch_metric_alarm" "dlq" {
  alarm_name          = "ateneo-inferencias-en-dlq"
  alarm_description   = "Hay trabajos de inferencia que fallaron 3 veces y quedaron en la DLQ."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.inferencias_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  alarm_actions       = local.alarma_comun.alarm_actions
  ok_actions          = local.alarma_comun.ok_actions
  treat_missing_data  = local.alarma_comun.treat_missing_data
}

# La cola no avanza: hay mensajes esperando hace más de 5 minutos (workers caídos o saturados).
resource "aws_cloudwatch_metric_alarm" "cola_atascada" {
  alarm_name          = "ateneo-inferencias-atascadas"
  alarm_description   = "El mensaje más viejo de la cola tiene más de 5 minutos."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.inferencias.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 300
  alarm_actions       = local.alarma_comun.alarm_actions
  ok_actions          = local.alarma_comun.ok_actions
  treat_missing_data  = local.alarma_comun.treat_missing_data
}

# El backend no tiene instancias sanas detrás del ALB.
resource "aws_cloudwatch_metric_alarm" "app_sin_sanas" {
  count             = var.encendido ? 1 : 0
  alarm_name        = "ateneo-app-sin-instancias-sanas"
  alarm_description = "tg-app no tiene ninguna instancia healthy."
  namespace         = "AWS/ApplicationELB"
  metric_name       = "HealthyHostCount"
  dimensions = {
    TargetGroup  = aws_lb_target_group.app.arn_suffix
    LoadBalancer = aws_lb.app[0].arn_suffix
  }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 5
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  alarm_actions       = local.alarma_comun.alarm_actions
  ok_actions          = local.alarma_comun.ok_actions
  treat_missing_data  = "breaching"
}
