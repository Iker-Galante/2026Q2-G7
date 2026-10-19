# Cómo crece y se achica cada servicio (sección 07 y riesgo 02 de la E2: medir el trabajo que
# espera, no el que se hace). La api escala por CPU; los otros tres, por su cola.
#
# worker y procesador usan backlog por tarea —mensajes esperando ÷ tareas corriendo—, que es la
# receta de AWS para consumidores de SQS: el umbral dice cuánto trabajo le toca a cada tarea, así
# que la decisión no cambia según cuántas tareas haya corriendo. El divisor es RunningTaskCount,
# que publica Container Insights: por eso está prendido (ecs.tf). Si el laboratorio no lo
# permite, `container_insights = false` los deja escalando por escalones sobre los mensajes
# visibles, sin dividir: suben de a una tarea por minuto mientras haya trabajo esperando.
#
# El evaluador no puede usar target tracking, que nunca arranca desde cero tareas: se queda con
# dos alarmas y ExactCapacity, que es exactamente el 0 ↔ 1 de la decisión 05.

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

locals {
  # servicio => su cola y cuántos mensajes esperando por tarea se toleran antes de agregar otra.
  por_backlog = var.container_insights ? {
    worker     = { cola = "inferencias", objetivo = var.mensajes_por_worker }
    procesador = { cola = "resultados", objetivo = 50 }
  } : {}

  # servicio => cola, umbral, y cuántos minutos de cola vacía antes de achicar. El evaluador
  # siempre; worker y procesador solo como repliegue, cuando no hay Container Insights.
  por_escalones = merge(
    {
      evaluador = { cola = "evaluaciones", umbral = 1, ajuste = "ExactCapacity", crecer = 1, achicar = 0, calma_min = 15 }
    },
    var.container_insights ? {} : {
      worker     = { cola = "inferencias", umbral = var.mensajes_por_worker, ajuste = "ChangeInCapacity", crecer = 1, achicar = -1, calma_min = 5 }
      procesador = { cola = "resultados", umbral = 50, ajuste = "ChangeInCapacity", crecer = 1, achicar = -1, calma_min = 10 }
    },
  )
}

# --- worker y procesador: backlog por tarea -------------------------------------------

resource "aws_appautoscaling_policy" "backlog" {
  for_each = local.por_backlog

  name               = "backlog-por-tarea-${each.value.cola}"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.s[each.key].service_namespace
  resource_id        = aws_appautoscaling_target.s[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.s[each.key].scalable_dimension

  target_tracking_scaling_policy_configuration {
    target_value = each.value.objetivo

    # Crecer rápido y achicar despacio: la tarea que se va tiene un mensaje entre manos, y
    # stopTimeout le da 60 s para terminarlo (ecs.tf).
    scale_out_cooldown = 60
    scale_in_cooldown  = 180

    customized_metric_specification {
      metrics {
        id          = "esperando"
        label       = "mensajes esperando en ${each.value.cola}"
        return_data = false

        metric_stat {
          stat = "Average"
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"
            dimensions {
              name  = "QueueName"
              value = module.colas[each.value.cola].nombre
            }
          }
        }
      }

      metrics {
        id          = "tareas"
        label       = "tareas corriendo de ${each.key}"
        return_data = false

        metric_stat {
          stat = "Average"
          metric {
            namespace   = "ECS/ContainerInsights"
            metric_name = "RunningTaskCount"
            dimensions {
              name  = "ClusterName"
              value = aws_ecs_cluster.ateneo.name
            }
            dimensions {
              name  = "ServiceName"
              value = aws_ecs_service.s[each.key].name
            }
          }
        }
      }

      # Los dos servicios tienen mínimo una tarea, así que el divisor nunca es cero. Si todavía
      # no hay dato (el primer minuto, o Container Insights recién prendido) la expresión no da
      # valor y la política no hace nada, que es lo que corresponde.
      metrics {
        id          = "backlog"
        label       = "mensajes esperando por tarea"
        expression  = "esperando / tareas"
        return_data = true
      }
    }
  }
}

# --- El evaluador (y el repliegue sin Container Insights): escalones ------------------

resource "aws_appautoscaling_policy" "crecer" {
  for_each = local.por_escalones

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
  for_each = local.por_escalones

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
  for_each = local.por_escalones

  alarm_name          = "ateneo-${each.key}-crecer"
  alarm_description   = "Hay mensajes esperando en ${each.value.cola}: una tarea más de ${each.key}."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = module.colas[each.value.cola].nombre }
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
  for_each = local.por_escalones

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
      dimensions  = { QueueName = module.colas[each.value.cola].nombre }
      period      = 60
      stat        = "Maximum"
    }
  }

  metric_query {
    id = "en_vuelo"
    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      dimensions  = { QueueName = module.colas[each.value.cola].nombre }
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
