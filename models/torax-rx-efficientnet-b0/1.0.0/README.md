# EfficientNet-B0 · Neumonía

Pesos preentrenados de ZubaerNiloy: https://huggingface.co/ZubaerNiloy/pneumonia-ensemble-onnx.
Revisión `d30e6fe12acc63248e0e669725e2d5944b541df1`, archivo `efficientnet_b0.onnx`. La ficha declara MIT;
se conserva la atribución al autor. Los pesos no se redistribuyen en Git: se
descargan y verifican con el manifiesto.

Entrada RGB float32 NCHW 224 × 224, normalización ImageNet; salida `logit`
con sigmoide, umbral 0.5 y clase positiva PNEUMONIA. El contrato corresponde
al código original de inferencia indicado en el manifiesto.

Se usa como modelo independiente, sin el ensemble del autor. Las métricas
se calculan en Ateneo sobre el conjunto reservado, no se copian del autor.
Es una demostración, no un dispositivo médico.
