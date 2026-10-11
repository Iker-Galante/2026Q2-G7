variable "region" {
  description = "El Learner Lab solo habilita todo en us-east-1."
  type        = string
  default     = "us-east-1"
}

variable "zonas" {
  description = "Las dos AZ: «a» y «b» de la guía. La subred de evaluación va solo en la primera."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.zonas) == 2
    error_message = "Hacen falta exactamente dos zonas."
  }
}

variable "encendido" {
  description = <<-EOT
    El interruptor de presupuesto (guía §14). false = la rutina de antes de End Lab:
    grupos en 0, eval-1 terminada, RDS detenida, sin NAT, sin balanceadores y sin endpoint de SQS.
    true = todo de vuelta. Las direcciones de los balanceadores cambian al recrearse, pero
    los .env y el CORS se regeneran solos.
  EOT
  type        = bool
  default     = true
}

variable "modo_inferencia" {
  description = <<-EOT
    "http": como hoy. El despachador del backend lleva cada trabajo al ALB interno.
    "sqs":  el backend encola en SQS y los workers consumen la cola. No hay ALB interno;
            hay un endpoint de interfaz de SQS para la subred sin internet.
  EOT
  type        = string
  default     = "sqs"

  validation {
    condition     = contains(["http", "sqs"], var.modo_inferencia)
    error_message = "modo_inferencia es \"http\" o \"sqs\"."
  }
}

variable "sufijo" {
  description = "Sufijo de los cinco buckets (únicos en todo AWS). Vacío = uno al azar, fijo desde el primer apply."
  type        = string
  default     = ""
}

variable "email_alertas" {
  description = "Mail que recibe las alarmas y el informe del guardián. Vacío = sin suscripción (el tema se crea igual)."
  type        = string
  default     = ""
}

variable "ami_worker_id" {
  description = "AMI dorada ya construida (ami-…). Vacío = Terraform la construye (imagen.tf)."
  type        = string
  default     = ""
}

variable "tipo_app" {
  type    = string
  default = "t3.small"
}

variable "tipo_worker" {
  description = "Si c5.large no está permitido en la cuenta, m5.large (guía §8.3)."
  type        = string
  default     = "c5.large"
}

variable "tipo_eval" {
  type    = string
  default = "c5.large"
}

variable "app_min" {
  type    = number
  default = 2
}

variable "app_max" {
  type    = number
  default = 3
}

variable "inf_min" {
  type    = number
  default = 1
}

variable "inf_max" {
  type    = number
  default = 2
}

variable "evaluador_activo" {
  description = "Si eval-1 existe mientras el sistema está encendido. false = solo la plantilla."
  type        = bool
  default     = true
}

variable "mensajes_por_worker" {
  description = "Modo sqs: cuántos mensajes en cola por instancia tolera el grupo antes de agregar otra."
  type        = number
  default     = 10
}

variable "guardian_activo" {
  description = "Lambda que todas las noches apaga lo que haya quedado prendido (red de seguridad del presupuesto)."
  type        = bool
  default     = true
}

variable "guardian_horario" {
  description = "Expresión de EventBridge en UTC. Por defecto 06:00 UTC = 03:00 en Argentina."
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "permitir_borrar_buckets" {
  description = "true solo al final del curso, para que terraform destroy pueda vaciar los buckets."
  type        = bool
  default     = false
}
