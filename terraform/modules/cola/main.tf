# Una cola de trabajo de Ateneo: la cola y su cola de fallidos, emparejadas en las dos
# direcciones. Existe como módulo porque la arquitectura (sección 08, decisión 03) dice que
# ninguna cola de trabajo va sin su cola de fallidos, y acá eso no se puede olvidar: las dos
# salen juntas o no sale ninguna.
#
# Las tres colas son estándar, no FIFO: todo consumidor es idempotente, así que alcanza con
# «al menos una vez».

# 14 días es el máximo de SQS: tiempo para mirar qué falló antes de que el mensaje se pierda.
resource "aws_sqs_queue" "fallidos" {
  name                      = "ateneo-${var.nombre}-dlq"
  message_retention_seconds = var.retencion_fallidos
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "cola" {
  name = "ateneo-${var.nombre}"

  visibility_timeout_seconds = var.visibilidad
  receive_wait_time_seconds  = var.espera
  message_retention_seconds  = var.retencion
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.fallidos.arn
    maxReceiveCount     = var.intentos
  })
}

# La otra mitad del par: la cola de fallidos solo acepta mensajes de esta cola, y solo a esta
# puede devolverlos. Sin esto, cualquier cola de la cuenta podría usarla de destino.
resource "aws_sqs_queue_redrive_allow_policy" "fallidos" {
  queue_url = aws_sqs_queue.fallidos.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.cola.arn]
  })
}
