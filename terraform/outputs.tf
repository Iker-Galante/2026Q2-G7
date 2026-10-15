output "url" {
  description = "El sitio, en S3. El login pasa por Cognito y la API por API Gateway."
  value       = local.url_sitio
}

output "api" {
  description = "API Gateway: /callback y /logout del login, y /api/* hacia el backend."
  value       = local.url_api
}

output "cognito_login" {
  description = "El Hosted UI de Cognito."
  value       = local.cognito_dominio
}

output "cognito_user_pool" {
  value = aws_cognito_user_pool.ateneo.id
}

output "alb" {
  description = "El backend sin pasar por API Gateway: solo para diagnóstico (pide token igual)."
  value       = var.encendido ? "http://${aws_lb.app[0].dns_name}" : "(apagado)"
}

output "buckets" {
  value = local.buckets
}

output "endpoint_rds" {
  value = aws_db_instance.ateneo.address
}

output "cola_inferencias" {
  value = aws_sqs_queue.inferencias.url
}

output "cola_inferencias_dlq" {
  value = aws_sqs_queue.inferencias_dlq.url
}

output "tema_alertas" {
  value = aws_sns_topic.alertas.arn
}

output "alb_interno" {
  value = local.alb_int_dns != "" ? "http://${local.alb_int_dns}:8081" : "(no hay: modo sqs o apagado)"
}

output "ami_worker" {
  value = local.ami_worker
}

output "eval_1" {
  value = one(aws_instance.eval[*].id)
}

output "vpce_s3" {
  value = aws_vpc_endpoint.s3.id
}
