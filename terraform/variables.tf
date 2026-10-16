variable "region" {
  description = "El Learner Lab solo habilita todo en us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "zonas" {
  description = "Las dos AZ. La subred de evaluación va solo en la primera (sección 06)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.zonas) == 2
    error_message = "Hacen falta exactamente dos zonas."
  }
}

variable "sufijo" {
  description = "Sufijo de los buckets y del dominio de Cognito (únicos en todo AWS). Vacío = uno al azar, fijo desde el primer apply."
  type        = string
  default     = ""
}

variable "email_admin" {
  description = "El admin_plataforma inicial. Cognito le manda una contraseña temporal. Vacío = sin admin (los admins se crean con Terraform)."
  type        = string
  default     = ""
}

variable "email_alertas" {
  description = "Recibe las alarmas de operación por SNS (colas de fallidos, 5xx del ALB). Vacío = sin suscripción."
  type        = string
  default     = ""
}

variable "datos_demo" {
  description = "El constructor siembra el modelo de la E2 en el bucket de modelos y el conjunto de 200 casos de Hugging Face en el de evaluación. Queda apretar «Publicar»."
  type        = bool
  default     = true
}

variable "waf_activo" {
  description = "WAF con reglas administradas de AWS en el ALB. false si el laboratorio no lo permite (sección 12)."
  type        = bool
  default     = true
}

variable "esperar_imagenes" {
  description = "Que el apply espere a que el constructor suba las imágenes antes de crear los servicios. Usa la CLI de AWS (está en CloudShell). false = ECS reintenta solo hasta que aparezcan."
  type        = bool
  default     = true
}

variable "container_insights" {
  description = <<-EOT
    Container Insights en el cluster de ECS. Prendido publica RunningTaskCount, el divisor del
    backlog por tarea con el que escalan worker y procesador (escalado.tf). Apagado, los dos caen
    a escalones sobre los mensajes visibles, sin dividir. false si el laboratorio no lo permite
    (sección 12).
  EOT
  type        = bool
  default     = true
}

variable "mensajes_por_worker" {
  description = "Mensajes esperando en `inferencias` por tarea del worker a partir de los cuales se agrega otra."
  type        = number
  default     = 10
}
