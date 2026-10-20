# ResNet-50 · Tumor cerebral

Pesos preentrenados de visheshallahabadi, publicados con su Space:
https://huggingface.co/spaces/visheshallahabadi/brain-tumor-detection.
Revisión `8d926d391ff8b0f32dbd70cf864dcfede6b75362`, archivo `brain_tumor_classifier.onnx`.
El Space declara Apache-2.0; se conserva la atribución al autor. Los pesos no se
redistribuyen en Git: se descargan y verifican con el manifiesto.

Clasifica cortes de RM cerebral en cuatro clases. Entrada RGB float32 NCHW
224 × 224 con normalización ImageNet; salida `output` en logits (softmax en
Ateneo). Es una ResNet-50: el grafo tiene 53 convoluciones y termina en
`GlobalAveragePool` → `Gemm`.

El `app.py` del autor nombra las salidas `glioma`, `healthy`, `meningioma`,
`pituitary`. El contrato conserva ese orden y llama `notumor` a `healthy` para
usar el mismo vocabulario que el conjunto reservado. Es un cambio de nombre, no
de índice.

La ficha no dice con qué datos se entrenó; el orden alfabético con `healthy`
sugiere otra compilación que la de Kaggle. Las métricas se calculan en Ateneo
sobre el conjunto reservado. Es una demostración, no un dispositivo médico.
