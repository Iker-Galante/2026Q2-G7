# Planes contra un proveedor simulado: prueban la lógica (modos, interruptor, .env) sin
# credenciales ni cuenta de AWS.   terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
  mock_data "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/LabRole" }
  }
  mock_data "aws_ec2_managed_prefix_list" {
    defaults = { id = "pl-63a5400a" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = {
      arn = "arn:aws:sqs:us-east-1:123456789012:ateneo-inferencias"
      url = "https://sqs.us-east-1.amazonaws.com/123456789012/ateneo-inferencias"
    }
  }
  mock_resource "aws_lb" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/alb-ateneo/0123456789abcdef"
      arn_suffix = "app/alb-ateneo/0123456789abcdef"
      dns_name   = "alb-ateneo-123.us-east-1.elb.amazonaws.com"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = {
      arn        = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/tg/0123456789abcdef"
      arn_suffix = "targetgroup/tg/0123456789abcdef"
    }
  }
  mock_resource "aws_launch_template" {
    defaults = { id = "lt-0123456789abcdef0", latest_version = 1 }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::ateneo-bucket" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:us-east-1:123456789012:function:ateneo-guardian" }
  }
  mock_resource "aws_cloudwatch_event_rule" {
    defaults = { arn = "arn:aws:events:us-east-1:123456789012:rule/ateneo-guardian-nocturno" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:us-east-1:123456789012:ateneo-alertas" }
  }
}

mock_provider "random" {}
mock_provider "archive" {}

variables {
  sufijo        = "prueba"
  ami_worker_id = "ami-0fedcba9876543210"
}

run "http_encendido" {
  command = apply
  variables {
    modo_inferencia = "http"
  }

  assert {
    condition     = length(aws_lb.inf) == 1 && length(aws_vpc_endpoint.sqs) == 0
    error_message = "En modo http tiene que haber ALB interno y no endpoint de SQS."
  }
  assert {
    condition     = length(aws_nat_gateway.ateneo) == 1 && aws_autoscaling_group.app.min_size == 2
    error_message = "Encendido: NAT y dos instancias de app."
  }
  assert {
    condition     = strcontains(aws_s3_object.env["backend"].content, "INFERENCIA_URL=http://")
    error_message = "El backend.env tiene que apuntar al ALB interno."
  }
  assert {
    condition     = !strcontains(aws_s3_object.env["worker"].content, "DATABASE_URL")
    error_message = "En modo http el worker no lleva credenciales de base."
  }
  assert {
    condition     = length(aws_instance.eval) == 1 && length(aws_instance.constructor) == 0
    error_message = "eval-1 existe y no se construye imagen si se pasó ami_worker_id."
  }
}

run "sqs_encendido" {
  command = apply
  variables {
    modo_inferencia = "sqs"
  }

  assert {
    condition     = length(aws_lb.inf) == 0 && length(aws_vpc_endpoint.sqs) == 1
    error_message = "En modo sqs no hay ALB interno y sí endpoint de SQS."
  }
  assert {
    condition     = aws_autoscaling_group.inf.health_check_type == "EC2" && length(aws_autoscaling_policy.inf_cola) == 1
    error_message = "En modo sqs el grupo de inferencia mira EC2 y escala por cola."
  }
  assert {
    condition     = strcontains(aws_s3_object.env["worker"].content, "COLA_INFERENCIAS_URL=https://sqs.")
    error_message = "El worker.env tiene que traer la URL de la cola."
  }
  assert {
    condition     = strcontains(aws_s3_object.env["backend"].content, "MODO_INFERENCIA=sqs")
    error_message = "En modo sqs el backend tiene que encolar en SQS."
  }
}

run "apagado" {
  command = apply
  variables {
    encendido = false
  }

  assert {
    condition     = length(aws_nat_gateway.ateneo) == 0 && length(aws_lb.app) == 0 && length(aws_lb.inf) == 0
    error_message = "Apagado: sin NAT ni balanceadores."
  }
  assert {
    condition     = aws_autoscaling_group.app.max_size == 0 && aws_autoscaling_group.inf.max_size == 0
    error_message = "Apagado: los dos grupos en 0."
  }
  assert {
    condition     = aws_rds_instance_state.ateneo.state == "stopped" && length(aws_instance.eval) == 0
    error_message = "Apagado: base detenida y eval-1 terminada."
  }
}

run "construye_la_imagen_si_no_hay_ami" {
  command = plan
  variables {
    ami_worker_id = ""
  }

  assert {
    condition     = length(aws_instance.constructor) == 1 && length(aws_ami_from_instance.worker) == 1
    error_message = "Sin ami_worker_id, Terraform construye la imagen dorada."
  }
}
