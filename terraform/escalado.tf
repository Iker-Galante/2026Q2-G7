# Cómo crece y se achica cada servicio (sección 07 y riesgo 02 de la E2: medir el trabajo que
# espera, no el que se hace). La api escala por CPU; los otros tres, por los mensajes de su cola.

resource "aws_appautoscaling_target" "s" {
  for_each = local.servicios

  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.ateneo.name}/${aws_ecs_service.s[each.key].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  min_capacity       = each.value.minimo
  max_capacity       = each.value.maximo
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "cpu-60"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.s["api"].service_namespace
  resource_id        = aws_appautoscaling_target.s["api"].resource_id
  scalable_dimension = aws_appautoscaling_target.s["api"].scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value       = 60
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

# Sin Container Insights no hay métrica de tareas corriendo para dividir, así que en lugar del
# backlog por tarea se escala por pasos: con trabajo esperando, una tarea más por minuto hasta
# el máximo; con la cola vacía (ni esperando ni en vuelo) un rato, una menos.
# El evaluador pasa de 0 a 1 con el primer mensaje y vuelve a 0 tras 15 minutos de cola vacía.
locals {
  por_cola = {
    worker     = { cola = "inferencias", umbral = var.mensajes_por_worker, ajuste = "ChangeInCapacity", crecer = 1, achicar = -1, calma_min = 5 }
    procesador = { cola = "resultados", umbral = 50, ajuste = "ChangeInCapacity", crecer = 1, achicar = -1, calma_min = 10 }
    evaluador  = { cola = "evaluaciones", umbral = 1, ajuste = "ExactCapacity", crecer = 1, achicar = 0, calma_min = 15 }
  }
}

resource "aws_appautoscaling_policy" "crecer" {
  for_each = local.por_cola

  name               = "crecer-por-${each.value.cola}"
  policy_type        = "StepScaling"
  service_namespace  = aws_appautoscaling_target.s[each.key].service_namespace
  resource_id        = aws_appautoscaling_target.s[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.s[each.key].scalable_dimension

  step_scaling_policy_configuration {
    adjustment_type         = each.value.ajuste
    cooldown                = 60
    metric_aggregation_type = "Maximum"
    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = each.value.crecer
    }
  }
}

resource "aws_appautoscaling_policy" "achicar" {
  for_each = local.por_cola

  name               = "achicar-por-${each.value.cola}"
  policy_type        = "StepScaling"
  service_namespace  = aws_appautoscaling_target.s[each.key].service_namespace
  resource_id        = aws_appautoscaling_target.s[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.s[each.key].scalable_dimension

  step_scaling_policy_configuration {
    adjustment_type         = each.value.ajuste
    cooldown                = 60
    metric_aggregation_type = "Maximum"
    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = each.value.achicar
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "cola_con_trabajo" {
  for_each = local.por_cola

  alarm_name          = "ateneo-${each.key}-crecer"
  alarm_description   = "Hay mensajes esperando en ${each.value.cola}: una tarea más de ${each.key}."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.cola[each.value.cola].name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = each.value.umbral
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_appautoscaling_policy.crecer[each.key].arn]
}

# Una cola inactiva deja de publicar métricas: sin datos cuenta como vacía.
resource "aws_cloudwatch_metric_alarm" "cola_vacia" {
  for_each = local.por_cola

  alarm_name          = "ateneo-${each.key}-achicar"
  alarm_description   = "${each.value.cola} vacía hace ${each.value.calma_min} minutos: una tarea menos de ${each.key}."
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  evaluation_periods  = each.value.calma_min
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_appautoscaling_policy.achicar[each.key].arn]

  metric_query {
    id = "visibles"
    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"
      dimensions  = { QueueName = aws_sqs_queue.cola[each.value.cola].name }
      period      = 60
      stat        = "Maximum"
    }
  }

  metric_query {
    id = "en_vuelo"
    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      dimensions  = { QueueName = aws_sqs_queue.cola[each.value.cola].name }
      period      = 60
      stat        = "Maximum"
    }
  }

  metric_query {
    id          = "total"
    expression  = "visibles + en_vuelo"
    label       = "mensajes en ${each.value.cola}"
    return_data = true
  }
}
