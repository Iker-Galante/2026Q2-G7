# Sección 08 y decisión 03: una cola por tipo de trabajo, cada una con su cola de fallidos.
# Son estándar (al menos una vez): todo consumidor es idempotente.
#
#   cola          publica              consume      invisible mientras se procesa   a fallidos tras
#   inferencias   api, procesador      worker       2 min                           3 intentos
#   evaluaciones  api                  evaluador    30 min, extendible              2 intentos
#   resultados    worker, evaluador    procesador   1 min                           5 intentos

locals {
  colas = {
    inferencias  = { visibilidad = 120, intentos = 3, retencion = 86400 }
    evaluaciones = { visibilidad = 1800, intentos = 2, retencion = 345600 }
    resultados   = { visibilidad = 60, intentos = 5, retencion = 345600 }
  }
}

resource "aws_sqs_queue" "fallidos" {
  for_each                  = local.colas
  name                      = "ateneo-${each.key}-dlq"
  message_retention_seconds = 1209600 # 14 días, el máximo: tiempo para mirar qué falló
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "cola" {
  for_each = local.colas
  name     = "ateneo-${each.key}"

  visibility_timeout_seconds = each.value.visibilidad
  receive_wait_time_seconds  = 20 # long polling: menos llamadas vacías
  message_retention_seconds  = each.value.retencion
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.fallidos[each.key].arn
    maxReceiveCount     = each.value.intentos
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "fallidos" {
  for_each  = local.colas
  queue_url = aws_sqs_queue.fallidos[each.key].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.cola[each.key].arn]
  })
}
