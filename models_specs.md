# Modelo de demostración disponible desde el primer despliegue

Estado: implementada con descarga verificada de pesos, según la aclaración del usuario.

Ajuste de alcance autorizado: la fuente no declara una licencia de redistribución. El usuario
eligió descargar los pesos con revisión y SHA-256 fijos en lugar de incluir el ONNX en Git.
Se versionan contrato y manifiesto; un clon nuevo requiere internet en su primera preparación.
Los requisitos de incluir el binario y funcionar sin descargar pesos quedan sustituidos por
esta decisión. El resto del documento conserva la especificación de referencia.

## Objetivo

Incluir en el repositorio el modelo de radiografía de tórax que ya se probó y automatizar su preparación para que una instalación nueva de Ateneo tenga un modelo publicado, evaluado y utilizable. El usuario entra al catálogo, abre su ficha y sube una radiografía para obtener una inferencia, sin descargar, subir ni publicar un modelo por su cuenta.

Aplica tanto al entorno local con Docker Compose como al despliegue en AWS Academy con Terraform. Esta especificación no autoriza ejecutar Terraform: esa operación requiere una solicitud explícita posterior.

## Qué significa «entrenado»

El archivo ONNX ya contiene un modelo preentrenado. Ateneo ejecuta inferencias y evalúa sus métricas; no entrena ni modifica sus pesos. La implementación debe automatizar la carga, publicación y evaluación del modelo existente. No debe inventar métricas ni marcarlo como evaluado sin ejecutar el evaluador.

## Modelo que se debe incluir

| Campo | Valor |
| --- | --- |
| Nombre | `torax-rx-neumonia` |
| Versión | `1.0.0` |
| Tipo de estudio | `torax-rx` |
| Tarea | Clasificación de radiografías de tórax |
| Clases | `NORMAL`, `PNEUMONIA` |
| Archivo de origen local | `tmp/modelo/modelo.onnx` |
| Contrato probado | `tmp/modelo/modelo.json` |
| Procedencia | `https://huggingface.co/Rhishamah/mediscan-pneumonia` |
| SHA-256 del ONNX probado | `208b1439d819fede1a4b43e49809d0ca77768ee66184e110c14df1eb838ea67f` |

Preservar el contrato probado: entrada `input`, NCHW RGB float32 de 224 × 224, escala 255, media y desvío de ImageNet; salida `output`, `logit_sigmoide`, clase positiva `PNEUMONIA`, umbral 0.5. La fuente de verdad será el contrato incluido junto al ONNX.

## Situación actual

- El README describe descargas y publicación manuales.
- `tools/descargar_modelo.py` descarga el ONNX y genera el contrato; opcionalmente copia ambos al bucket.
- `tmp/` y los archivos `*.onnx` están ignorados por Git. Los archivos que se usaron en esta PC no aparecen en un clon nuevo.
- Docker Compose crea los servicios y buckets, pero no carga ni publica el modelo automáticamente.
- El constructor de AWS, con `datos_demo = true`, carga el modelo y el conjunto en S3, pero deja pendiente pulsar «Publicar».
- Subir objetos al bucket no alcanza: también debe existir el registro del catálogo y debe encolarse la evaluación mediante el flujo del backend.
- El estado y los resultados obtenidos manualmente en esta PC no deben convertirse en un volcado de base de datos para distribuir.

## Archivos versionados

Crear `models/torax-rx-neumonia/1.0.0/` con:

- `modelo.onnx`: copia exacta del archivo probado, de unos 16 MB.
- `modelo.json`: contrato correspondiente.
- `manifest.json`: nombre, versión, origen, revisión de origen cuando pueda identificarse, tamaño y SHA-256 de los artefactos.
- `README.md`: procedencia, uso previsto, contrato y condiciones de redistribución verificadas en la fuente.

Versionar el ONNX directamente en Git por su tamaño actual; agregar una excepción acotada en `.gitignore` para ese archivo. No habilitar todos los ONNX ni incluir `tmp/`, credenciales, estados de Terraform o datos de pacientes. Verificar la licencia y conservar las atribuciones aplicables antes de redistribuir el binario; si la fuente no permite determinar el permiso de redistribución, informar el bloqueo y no afirmar que el artefacto quedó distribuido.

Una instalación nueva debe obtener el modelo desde el repositorio, sin depender de descargar sus pesos desde Hugging Face durante el arranque. No usar Git LFS de forma implícita ni dejar un puntero en lugar del binario. Un cambio de pesos o de contrato incompatible requiere una nueva versión.

## Inicialización automática

Separar dos responsabilidades para evitar dependencias circulares y compartirlas entre local y AWS:

1. **Preparar artefactos:** validar hashes, copiar el ONNX y contrato al bucket de modelos y preparar/cargar el conjunto de evaluación.
2. **Registrar el modelo:** con migraciones aplicadas y artefactos completos, reutilizar `PublicarModelo` para registrarlo y encolar su evaluación. El evaluador y el procesador completan el flujo normal de resultados.

El registro debe ejecutarse como operación interna de inicialización, sin simular un usuario, guardar tokens de Cognito, abrir endpoints públicos de administración ni insertar métricas mediante SQL.

### Conjunto de evaluación

Usar el conjunto de demostración `torax-rx/v1`: 200 casos del split `test` de `hf-vision/chest-xray-pneumonia`, 100 por clase, semilla 42, generado con `tools/preparar_conjunto.py` y cargado con `tools/subir_conjunto.py`.

La descarga del conjunto puede requerir internet en la primera preparación. Conservarlo en almacenamiento persistente para evitar repetir la descarga y conversión en cada arranque. Registrar procedencia, selección y hash del conjunto preparado en su manifiesto; fijar una revisión de origen cuando el mecanismo de descarga lo permita. No prometer reproducibilidad binaria solo por usar una semilla: el script actual genera nombres UUID aleatorios.

Subir todos los casos y `verdad.jsonl` antes de publicar `manifiesto.json`, que actuará como marca de finalización. Verificar que el manifiesto corresponda a los archivos presentes; su sola existencia no garantiza una carga íntegra. Las etiquetas y casos reservados no se exponen a través del catálogo público.

### Docker Compose

- Agregar un servicio de inicialización de artefactos, sin puertos, que arranque por defecto y use la imagen de herramientas/ML con el modelo versionado incluido.
- Esperar a que MinIO esté sano y los buckets existan. No condicionar el arranque de worker, evaluador y procesador a que la evaluación ya haya terminado.
- Mantener el conjunto preparado en un volumen o caché persistente; no depender del contenido actual de `tmp/`.
- Incorporar en el procesador una rutina de registro que espere la disponibilidad de artefactos completos y publique una sola vez. Debe convivir con el consumo de resultados y tener reintentos acotados con espera.
- El comando habitual `docker compose up -d --build` debe iniciar todo el proceso sin comandos manuales adicionales.
- Agregar un comando de verificación/espera que termine correctamente solo cuando el modelo esté en `ok`, o falle con un motivo y un límite de tiempo configurable. Documentar que Compose puede devolver antes de que termine la evaluación inicial.

### AWS Academy

- Mantener `datos_demo` como control del proceso completo. Con `true`, preparar artefactos y publicar automáticamente; con `false`, no sembrar ni registrar automáticamente. Desactivarlo no elimina modelos ya existentes.
- Reutilizar el constructor para copiar el modelo versionado y preparar el conjunto; dejar de descargar sus pesos desde la URL externa.
- Incluir `models/` en el paquete de despliegue y en el cálculo de hash. El empaquetado actual usa `file()` para leer fuentes de texto: no pasar el ONNX por esa función. Adaptar el empaquetado a archivos binarios preservando una lista explícita de archivos permitidos y excluyendo secretos y estado.
- Incluir los artefactos en las imágenes que los necesiten, actualizando Dockerfiles y contexto según corresponda.
- Pasar la configuración de inicialización al procesador y reutilizar la rutina interna de registro, sin llamar a la API con credenciales de un administrador.
- Mantener al constructor independiente de ECS/RDS para el registro: primero prepara S3; el procesador registra cuando sus dependencias están listas.
- Exponer claramente errores de preparación y de registro. No considerar «modelo listo» solo porque Terraform terminó o las imágenes ya existen.

## Idempotencia, concurrencia y recuperación

- Identificar el modelo por `(nombre, version)` y comprobar el hash del artefacto.
- Si el mismo modelo está en `ok`, conservar su ID, métricas, fechas y objetos. No republicar ni reevaluar al reiniciar.
- Si está `pendiente` o `en_curso`, dejar continuar la evaluación existente; no ejecutar `PublicarModelo` otra vez sobre esos estados.
- Proteger la decisión de alta frente a dos procesadores concurrentes mediante bloqueo en PostgreSQL y la unicidad de nombre/versión. No bloquear el consumo de resultados durante toda la evaluación.
- Si falta algún objeto, reparar la carga desde los artefactos versionados sin sobrescribir una versión distinta bajo la misma identidad. Ante un hash incompatible, fallar explícitamente.
- Recuperar fallos de encolado y evaluaciones atascadas usando estados persistidos, reintentos limitados y los mecanismos de vencimiento existentes. Un estado `pendiente` sin mensaje no debe quedar detenido para siempre.
- Si la evaluación termina en error, registrar el motivo y permitir una recuperación controlada; evitar ciclos infinitos de republicación y consumo de recursos.
- Una inicialización fallida no debe borrar modelos de usuarios ni inutilizar los servicios existentes.

## Comportamiento en la página

- Con el entorno listo, la portada y `/modelos` muestran el modelo real con métricas calculadas; su ficha permite subir una radiografía y consultar.
- Durante la primera preparación/evaluación, mostrar un mensaje comprensible de preparación automática. Evitar que una instalación en preparación parezca un catálogo vacío que exige publicar manualmente.
- Refrescar automáticamente el catálogo durante la inicialización hasta obtener el estado final, sin exigir recargar el navegador; detener o espaciar las consultas al terminar.
- En caso de error, informar que el modelo de demostración no pudo prepararse y ofrecer una indicación útil, sin mostrar datos sensibles.
- Conservar la publicación de modelos propios y los permisos actuales. El catálogo sigue siendo público; en AWS, consultar un estudio conserva el requisito de autenticación correspondiente.
- No llamar «entrenamiento» a la carga o evaluación ni mostrar resultados clínicos ficticios.

## Criterios de aceptación y verificación

1. En un clon limpio, el ONNX y contrato versionados existen y coinciden con el manifiesto. ONNX Runtime puede cargar el modelo.
2. En un entorno local aislado, con base y buckets nuevos, un único `docker compose up -d --build` prepara el conjunto, copia el modelo, lo publica y termina su evaluación sin intervención en `/publicar`.
3. El comando de espera confirma el estado `ok`; `GET /api/publico/modelos` devuelve una sola entrada para `torax-rx-neumonia` versión `1.0.0` con métricas reales.
4. Al abrir la web durante el arranque se informa la preparación; al terminar aparece el modelo sin recarga manual. Un usuario puede abrir su ficha y realizar una inferencia con una imagen compatible.
5. Reiniciar o reconstruir el entorno persistente conserva el mismo ID y métricas, sin duplicados, descargas innecesarias ni nuevas evaluaciones.
6. El modelo que el usuario ya publicó en esta PC se reconoce y conserva; no se borra ni se reemplaza para demostrar un arranque limpio.
7. Dos inicializaciones simultáneas no crean registros o evaluaciones duplicados. Probar también una carga incompleta y un fallo de encolado con recuperación.
8. Agregar pruebas dirigidas a la inicialización y su idempotencia. Ejecutar las pruebas existentes afectadas; la validación local no requiere desplegar AWS.
9. Para AWS, validar Terraform y el contenido binario del paquete construido; documentar la verificación real del Lab como pendiente si no se autorizó ese despliegue.
10. Actualizar README y documentación de Terraform con el arranque automático, la espera inicial, el mecanismo de recuperación y el carácter opcional de publicar otro modelo.

Usar volúmenes y un proyecto Compose separados para probar instalaciones nuevas. No ejecutar `docker compose down -v` sobre el entorno del usuario ni destruir recursos de AWS como parte de estas pruebas.

## Alcance de esta entrega documental

La implementación incluye inicialización de artefactos, registro automático con outbox, estado público, actualización del catálogo, comando de espera, recuperación explícita y pruebas locales. Terraform se valida con proveedores simulados; el despliegue real en AWS sigue pendiente de autorización.

### Verificación realizada

- 115 pruebas Python aprobadas, incluidas integración con PostgreSQL, dos procesadores concurrentes, recuperación de envíos e integridad de artefactos.
- Terraform validado y cinco pruebas con proveedores simulados aprobadas. ZIP local comprobado.
- Instalación aislada desde cero: descarga fijada, preparación de 200 casos, publicación y evaluación automáticas; resultado `ok`, accuracy 0.97. Inferencia real completada.
- Repetir la preparación y reiniciar conserva ID, fechas y métricas sin reevaluación. El modelo que el usuario publicó manualmente se conservó sin cambios.
- Entorno habitual actualizado y comando de espera confirmado en `ok`.
- Revisión visual no realizada por falta de navegador integrado disponible. Despliegue real en AWS no realizado.
