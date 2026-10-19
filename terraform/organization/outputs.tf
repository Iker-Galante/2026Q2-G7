output "url" {
  description = "El sitio, en S3. La verificación es abrirlo y entrar."
  value       = local.url_sitio
}

output "api" {
  description = "API Gateway: /callback y /logout del login, y /api/* hacia el ALB interno."
  value       = local.url_api
}

output "admin" {
  description = "El admin_plataforma inicial: Cognito le mandó una contraseña temporal."
  value       = var.email_admin != "" ? var.email_admin : "(sin admin: poné email_admin en terraform.tfvars)"
}

output "cognito_login" {
  value = local.cognito_dominio
}

output "cognito_user_pool" {
  value = aws_cognito_user_pool.ateneo.id
}

output "version_codigo" {
  description = "La etiqueta de las imágenes que corren."
  value       = local.version_codigo
}

output "como_ver_el_avance" {
  description = "La primera vez, las tareas tardan unos minutos en quedar sanas después del apply."
  value       = <<-EOT
    aws ecs describe-services --region ${var.region} --cluster ${aws_ecs_cluster.ateneo.name} --services ${join(" ", keys(local.servicios))} --query 'services[].[serviceName,runningCount,desiredCount]' --output table
    aws logs tail /ecs/ateneo/api --region ${var.region} --follow
    aws s3 cp s3://${local.buckets.artefactos}/logs/constructor-${local.version_codigo}.log -
  EOT
}

output "buckets" {
  value = local.buckets
}

output "colas" {
  value = { for k, c in module.colas : k => c.url }
}

output "endpoint_rds" {
  value = aws_db_instance.ateneo.address
}
