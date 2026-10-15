# API Gateway (HTTP API): la puerta HTTPS del sistema. Sin dominio propio ni CloudFront (el lab
# no los concede), es la única forma de tener un certificado válido sin pagar nada fijo.
#   GET /callback, GET /logout → Lambda: los pasos 3 y 4 del login (cognito.tf)
#   GET /api/health            → backend, sin token: la barra del sitio muestra si la API contesta
#   GET|POST /api/{proxy+}     → backend, con el access token validado por el autorizador JWT
# Las rutas al backend existen solo con encendido = true: apagado no hay ALB al que reenviar,
# pero el login y el sitio siguen en pie.

resource "aws_apigatewayv2_api" "ateneo" {
  name          = "ateneo"
  protocol_type = "HTTP"

  # El sitio vive en otro origen (S3). API Gateway contesta él mismo los preflight OPTIONS
  # cuando ninguna ruta los toma: por eso las rutas son GET y POST y no ANY, que mandaría el
  # OPTIONS al autorizador y el navegador vería un 401 sin cabeceras de CORS.
  cors_configuration {
    allow_origins = [local.url_sitio]
    allow_methods = ["GET", "POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.ateneo.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = 50
    throttling_burst_limit = 100
  }
}

locals {
  url_api      = aws_apigatewayv2_api.ateneo.api_endpoint # https://<id>.execute-api.<región>.amazonaws.com
  url_callback = "${local.url_api}/callback"
  url_logout   = "${local.url_api}/logout"
}

# --- Login: la Lambda del callback ----------------------------------------------------

data "archive_file" "callback" {
  type        = "zip"
  source_file = "${path.module}/lambda/callback.py"
  output_path = "${path.module}/.build/callback.zip"
}

resource "aws_cloudwatch_log_group" "callback" {
  name              = "/aws/lambda/ateneo-callback"
  retention_in_days = 14
}

# Sin VPC: tiene que llegar al endpoint de tokens de Cognito, que está en internet.
resource "aws_lambda_function" "callback" {
  function_name    = "ateneo-callback"
  role             = data.aws_iam_role.lab.arn
  runtime          = "python3.12"
  handler          = "callback.handler"
  filename         = data.archive_file.callback.output_path
  source_code_hash = data.archive_file.callback.output_base64sha256
  timeout          = 15
  depends_on       = [aws_cloudwatch_log_group.callback]

  environment {
    variables = {
      COGNITO_DOMINIO = local.cognito_dominio
      CLIENTE_ID      = aws_cognito_user_pool_client.web.id
      CLIENTE_SECRETO = aws_cognito_user_pool_client.web.client_secret
      URL_CALLBACK    = local.url_callback # tiene que ser idéntica a la del pedido de /authorize
      URL_SITIO       = local.url_sitio
    }
  }
}

# Permiso basado en recurso, como el del guardián: API Gateway invoca sin rol propio.
resource "aws_lambda_permission" "callback" {
  statement_id  = "apigateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.callback.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ateneo.execution_arn}/*/*"
}

resource "aws_apigatewayv2_integration" "callback" {
  api_id                 = aws_apigatewayv2_api.ateneo.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.callback.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "login" {
  for_each  = toset(["GET /callback", "GET /logout"])
  api_id    = aws_apigatewayv2_api.ateneo.id
  route_key = each.key
  target    = "integrations/${aws_apigatewayv2_integration.callback.id}"
}

# --- La API: proxy al ALB con el token validado ---------------------------------------

# Firma, emisor, vencimiento y cliente. Un access token de Cognito no trae aud: API Gateway
# compara la audiencia contra su client_id.
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.ateneo.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = local.cognito_emisor
    audience = [aws_cognito_user_pool_client.web.id]
  }
}

locals {
  # ruta => [camino en el backend, ¿pide token?]
  rutas_backend = {
    "GET /api/health"    = ["/api/health", false]
    "GET /api/{proxy+}"  = ["/api/{proxy}", true]
    "POST /api/{proxy+}" = ["/api/{proxy}", true]
  }
}

# HTTP_PROXY reenvía método, cabeceras (Authorization incluida) y query string tal cual.
resource "aws_apigatewayv2_integration" "backend" {
  for_each           = var.encendido ? toset(["/api/health", "/api/{proxy}"]) : toset([])
  api_id             = aws_apigatewayv2_api.ateneo.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = "http://${aws_lb.app[0].dns_name}${each.key}"
}

resource "aws_apigatewayv2_route" "backend" {
  for_each           = { for ruta, v in local.rutas_backend : ruta => v if var.encendido }
  api_id             = aws_apigatewayv2_api.ateneo.id
  route_key          = each.key
  target             = "integrations/${aws_apigatewayv2_integration.backend[each.value[0]].id}"
  authorization_type = each.value[1] ? "JWT" : "NONE"
  authorizer_id      = each.value[1] ? aws_apigatewayv2_authorizer.cognito.id : null
}
