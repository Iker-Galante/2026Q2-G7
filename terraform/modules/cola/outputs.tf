output "url" {
  description = "La URL de la cola: es lo que leen los servicios de ECS por variable de entorno."
  value       = aws_sqs_queue.cola.url
}

output "arn" {
  description = "El ARN de la cola."
  value       = aws_sqs_queue.cola.arn
}

output "nombre" {
  description = "El nombre de la cola, que es la dimensión QueueName de las métricas de CloudWatch con las que escalan los servicios."
  value       = aws_sqs_queue.cola.name
}

output "url_fallidos" {
  description = "La URL de la cola de fallidos."
  value       = aws_sqs_queue.fallidos.url
}

output "arn_fallidos" {
  description = "El ARN de la cola de fallidos."
  value       = aws_sqs_queue.fallidos.arn
}

output "nombre_fallidos" {
  description = "El nombre de la cola de fallidos, para la alarma que avisa cuando algo cayó ahí."
  value       = aws_sqs_queue.fallidos.name
}

output "redrive_policy" {
  description = "La política de reintentos tal como quedó en la cola, con el destino y la cantidad de intentos."
  value       = aws_sqs_queue.cola.redrive_policy
}
