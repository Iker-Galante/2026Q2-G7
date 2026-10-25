# Modelo de demostración

Modelo preentrenado de Rhishamah: https://huggingface.co/Rhishamah/mediscan-pneumonia
Revisión: `f31fffeac0caa11017df1b0948cc54f73a05033e`.

El manifiesto fija URL, tamaño y SHA-256 del ONNX probado. El contrato describe
su entrada y salida; las métricas se calculan con el evaluador de Ateneo.

La fuente no declara licencia de redistribución (verificados la API del modelo
y `model_card.md`). Por decisión del usuario, se versionan contrato y manifiesto,
pero no los pesos. La primera instalación descarga y verifica el binario;
las siguientes reutilizan S3/MinIO o la caché persistente. No se necesita una
cuenta de Hugging Face. La conectividad es necesaria en la primera preparación.

Es una demostración de clasificación NORMAL/PNEUMONIA en radiografías de tórax.
La ficha de origen lo califica como experimental y documenta sesgos; no es un
dispositivo médico ni corresponde presentar su evaluación como entrenamiento.
