# SQS: la cola interna de inferencias, con su cola de mensajes muertos.
#
# Reemplaza a la tabla-cola con SKIP LOCKED, al despachador y al barrido de huérfanos:
#   - un mensaje que un worker tomó y no borró (porque murió, o porque falló) vuelve a ser
#     visible solo al vencer visibility_timeout: los huérfanos dejan de existir;
#   - los reintentos los cuenta SQS (ApproximateReceiveCount) y al tercero el mensaje pasa
#     a la DLQ, donde una alarma avisa por SNS (notificaciones.tf);
#   - el grupo de inferencia escala por mensajes en cola, no solo por CPU (inferencia.tf).
# La tabla trabajo sigue siendo la fuente de verdad del estado que ve la pantalla.

resource "aws_sqs_queue" "inferencias_dlq" {
  name                      = "ateneo-inferencias-dlq"
  message_retention_seconds = 1209600 # 14 días, el máximo: tiempo para mirar qué falló
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "inferencias" {
  name = "ateneo-inferencias"

  # Más que el timeout de una inferencia (30 s) con margen: si el worker no borra el mensaje
  # en este tiempo, otro lo toma.
  visibility_timeout_seconds = 90
  receive_wait_time_seconds  = 20    # long polling: menos llamadas vacías
  message_retention_seconds  = 86400 # un trabajo de más de un día ya no le sirve a nadie
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.inferencias_dlq.arn
    maxReceiveCount     = 3 # la misma regla de los 3 intentos del dominio
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "inferencias_dlq" {
  queue_url = aws_sqs_queue.inferencias_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.inferencias.arn]
  })
}
