# `modules/cola`

Una cola de trabajo de Ateneo: la cola y su cola de fallidos, emparejadas en las dos direcciones.

Existe como módulo porque la arquitectura (sección 08, decisión 03) dice que ninguna cola de
trabajo va sin su cola de fallidos. Acá eso no se puede olvidar: los tres recursos salen juntos o
no sale ninguno, y la relación entre los dos queda escrita una sola vez.

- `aws_sqs_queue.cola` — `ateneo-<nombre>`. Estándar, no FIFO: todo consumidor es idempotente, así
  que alcanza con «al menos una vez». Cifrado con las claves que administra SQS, long polling de
  20 segundos por defecto y una `redrive_policy` que manda a la cola de fallidos tras `intentos`
  entregas.
- `aws_sqs_queue.fallidos` — `ateneo-<nombre>-dlq`. Retiene 14 días, el máximo de SQS: un mensaje
  que agotó sus intentos es algo para mirar, no para perder.
- `aws_sqs_queue_redrive_allow_policy.fallidos` — la otra mitad del par. La cola de fallidos solo
  acepta mensajes de esta cola y solo a esta puede devolverlos; sin esto, cualquier cola de la
  cuenta podría usarla de destino.

El root lo llama una vez por tipo de trabajo, con `for_each` sobre `local.colas`
(`organization/colas.tf`): inferencias, evaluaciones y resultados.

```hcl
module "colas" {
  source   = "../modules/cola"
  for_each = local.colas

  nombre      = each.key
  visibilidad = each.value.visibilidad
  intentos    = each.value.intentos
  retencion   = each.value.retencion
}
```

<!-- BEGIN_TF_DOCS -->
<!-- La tabla de entradas, salidas y recursos la genera terraform-docs en el PR
     (.github/workflows/terraform-docs.yml de la plantilla de la cátedra). -->
<!-- END_TF_DOCS -->
