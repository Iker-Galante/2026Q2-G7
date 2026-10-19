# Decisión 01 y 12: el ALB interno reparte entre las tareas de la api y les hace health check.
# Sin IP pública: solo lo alcanza el VPC Link de API Gateway. El WAF va acá porque no se puede
# asociar a una HTTP API, y por el ALB pasa todo lo que entra.

resource "aws_lb" "interno" {
  name               = "ateneo-interno"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [local.sg["alb"]]
  subnets            = local.sub["aplicacion"]

  # Un encabezado HTTP malformado se tira acá en vez de llegar a la api. Es gratis y cierra la
  # clase de ataques que mete dos encabezados y se aprovecha de que el proxy y el servidor no
  # interpreten igual cuál vale.
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name                 = "ateneo-api"
  port                 = 8080
  protocol             = "HTTP"
  target_type          = "ip" # Fargate: cada tarea tiene su propia interfaz
  vpc_id               = aws_vpc.ateneo.id
  deregistration_delay = 30

  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.interno.arn
  port              = 80
  protocol          = "HTTP" # tramo dentro de la VPC entre grupos encadenados (riesgo 09)

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- WAF ------------------------------------------------------------------------------

locals {
  # Las reglas administradas de AWS: inyección SQL, entradas maliciosas conocidas y lo común.
  reglas_waf = ["AWSManagedRulesCommonRuleSet", "AWSManagedRulesKnownBadInputsRuleSet", "AWSManagedRulesSQLiRuleSet"]
}

resource "aws_wafv2_web_acl" "alb" {
  count = var.waf_activo ? 1 : 0
  name  = "ateneo"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  dynamic "rule" {
    for_each = local.reglas_waf
    content {
      name     = rule.value
      priority = rule.key + 1

      override_action {
        none {}
      }

      statement {
        managed_rule_group_statement {
          name        = rule.value
          vendor_name = "AWS"
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = rule.value
        sampled_requests_enabled   = true
      }
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "ateneo"
    sampled_requests_enabled   = true
  }
}

resource "aws_wafv2_web_acl_association" "alb" {
  count        = var.waf_activo ? 1 : 0
  resource_arn = aws_lb.interno.arn
  web_acl_arn  = aws_wafv2_web_acl.alb[0].arn
}
