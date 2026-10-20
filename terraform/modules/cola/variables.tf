variable "nombre" {
  description = "El tipo de trabajo: inferencias, evaluaciones, resultados. Da el nombre de las dos colas."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.nombre))
    error_message = "Minúsculas, dígitos y guiones, entre 3 y 41 caracteres: es parte del nombre de una cola de SQS."
  }
}

variable "visibilidad" {
  description = "Segundos que un mensaje queda invisible mientras alguien lo procesa. Tiene que superar lo que tarda el consumidor más lento, o el mensaje se entrega dos veces."
  type        = number

  validation {
    condition     = var.visibilidad >= 0 && var.visibilidad <= 43200
    error_message = "SQS admite entre 0 segundos y 12 horas (43200)."
  }
}

variable "intentos" {
  description = "Entregas antes de que el mensaje pase a la cola de fallidos."
  type        = number

  validation {
    condition     = var.intentos >= 1 && var.intentos <= 1000
    error_message = "Entre 1 y 1000 intentos."
  }
}

variable "retencion" {
  description = "Segundos que la cola guarda un mensaje sin consumir antes de tirarlo."
  type        = number

  validation {
    condition     = var.retencion >= 60 && var.retencion <= 1209600
    error_message = "SQS admite entre 1 minuto y 14 días (1209600 segundos)."
  }
}

variable "retencion_fallidos" {
  description = "Lo mismo, para la cola de fallidos. Por defecto el máximo: un mensaje que agotó sus intentos es algo para mirar, no para perder."
  type        = number
  default     = 1209600
}

variable "espera" {
  description = "Segundos de long polling al recibir. Con 0, el consumidor hace llamadas vacías y paga por cada una."
  type        = number
  default     = 20
}
