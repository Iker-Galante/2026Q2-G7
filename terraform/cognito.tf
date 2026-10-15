# Cognito: usuarios y login administrado (Hosted UI). El login sigue el recorrido de la clase:
#   1. el navegador abre el sitio en S3, por HTTP (s3.tf)
#   2. el sitio redirige al Hosted UI de Cognito
#   3. Cognito vuelve a GET /callback de API Gateway, que es HTTPS: Cognito no acepta un
#      callback HTTP, y sin dominio propio ni CloudFront el sitio en S3 no puede ser HTTPS
#   4. la Lambda canjea el código por los tokens y redirige al sitio con los tokens en el
#      fragmento: http://<sitio>/#access_token=… (api.tf, lambda/callback.py)
#   5. el sitio los lee de la URL y los guarda en localStorage
#   6. cada pedido a la API lleva el access token; API Gateway lo valida antes de reenviarlo
#      al ALB, y el backend lo vuelve a validar (el ALB sigue siendo público)

resource "aws_cognito_user_pool" "ateneo" {
  name = "ateneo"

  # El email es el nombre de usuario, y Cognito lo verifica con un código antes de dejar entrar.
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Cualquiera se registra desde el Hosted UI. Con el remitente de Cognito salen hasta 50 mails
  # por día (verificación y cambio de contraseña): alcanza para la demo.
  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  deletion_protection = "INACTIVE" # terraform destroy tiene que poder borrarlo
}

# El prefijo es único en toda la región, como los nombres de bucket: lleva el mismo sufijo.
resource "aws_cognito_user_pool_domain" "ateneo" {
  domain                = "ateneo-${local.sufijo}"
  user_pool_id          = aws_cognito_user_pool.ateneo.id
  managed_login_version = 1 # Hosted UI clásico; el 2 (managed login) exige además un recurso de branding
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "ateneo-web"
  user_pool_id = aws_cognito_user_pool.ateneo.id

  # Cliente confidencial: el secreto lo tiene solo la Lambda del callback, que es la que canjea
  # el código. El navegador nunca lo ve.
  generate_secret = true

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

  # Las dos en API Gateway (HTTPS). La de logout también: la Lambda rebota al sitio.
  callback_urls = [local.url_callback]
  logout_urls   = [local.url_logout]

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}

locals {
  cognito_dominio = "https://${aws_cognito_user_pool_domain.ateneo.domain}.auth.${var.region}.amazoncognito.com"
  cognito_emisor  = "https://${aws_cognito_user_pool.ateneo.endpoint}" # iss de los tokens
}
