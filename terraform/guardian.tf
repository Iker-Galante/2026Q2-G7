# Lambda + EventBridge: red de seguridad del presupuesto de USD 100 (guía §14).
# Usa LabRole como rol de ejecución: en el Learner Lab no se pueden crear roles.

data "archive_file" "guardian" {
  type        = "zip"
  source_file = "${path.module}/lambda/guardian.py"
  output_path = "${path.module}/.build/guardian.zip"
}

resource "aws_lambda_function" "guardian" {
  count            = var.guardian_activo ? 1 : 0
  function_name    = "ateneo-guardian"
  role             = data.aws_iam_role.lab.arn
  runtime          = "python3.12"
  handler          = "guardian.handler"
  filename         = data.archive_file.guardian.output_path
  source_code_hash = data.archive_file.guardian.output_base64sha256
  depends_on       = [aws_cloudwatch_log_group.guardian]
  timeout          = 300 # borrar el NAT y liberar su IP lleva un par de minutos

  environment {
    variables = {
      GRUPOS     = "${aws_autoscaling_group.app.name},${aws_autoscaling_group.inf.name}"
      RDS_ID     = aws_db_instance.ateneo.identifier
      VPC_ID     = aws_vpc.ateneo.id
      TEMA_SNS   = aws_sns_topic.alertas.arn
      BORRAR_NAT = "true"
    }
  }
}

resource "aws_cloudwatch_log_group" "guardian" {
  count             = var.guardian_activo ? 1 : 0
  name              = "/aws/lambda/ateneo-guardian"
  retention_in_days = 14
}

resource "aws_cloudwatch_event_rule" "guardian" {
  count               = var.guardian_activo ? 1 : 0
  name                = "ateneo-guardian-nocturno"
  description         = "Apaga lo que haya quedado prendido"
  schedule_expression = var.guardian_horario
}

resource "aws_cloudwatch_event_target" "guardian" {
  count = var.guardian_activo ? 1 : 0
  rule  = aws_cloudwatch_event_rule.guardian[0].name
  arn   = aws_lambda_function.guardian[0].arn
}

# Permiso basado en recurso: EventBridge invoca la función sin necesitar un rol propio.
resource "aws_lambda_permission" "guardian" {
  count         = var.guardian_activo ? 1 : 0
  statement_id  = "eventbridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.guardian[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.guardian[0].arn
}
