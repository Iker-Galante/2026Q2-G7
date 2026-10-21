# EfficientNetB3 · Tumor cerebral

Pesos preentrenados de Udit013: https://huggingface.co/Udit013/brain-tumor-efficientnetb3.
Revisión `31a6602d40ea14a1e012855c4529326d06f9c126`, archivo `efficientnetb3.onnx`. La ficha declara MIT;
se conserva la atribución al autor. Los pesos no se redistribuyen en Git: se
descargan y verifican con el manifiesto.

Clasifica cortes de RM cerebral en cuatro clases: `glioma`, `meningioma`,
`notumor` y `pituitary` (adenoma de hipófisis). Reproduce el mejor modelo de un
trabajo del IEEE (DOI 10.1109/ICC-ROBINS60238.2024.10533941); el código está en
https://github.com/Udit013/Brain_Tumor_Classificatioin.

Entrada RGB float32 NHWC 256 × 256 con los píxeles crudos en [0, 255]: el grafo
reescala y normaliza adentro. Salida `dense_2`, ya pasada por softmax, en el
orden alfabético de clases de `src/btc/config.py`. El contrato corresponde a esa
configuración; no se tocó para mejorar resultados. El archivo `temperature.json`
del autor (calibración) no cambia la clase elegida y no se usa.

El autor documenta que el dataset de Kaggle con el que se entrenó tiene fuga
entre train y test (casi-duplicados). Las métricas de Ateneo se miden sobre ese
mismo test, así que tienden a ser optimistas. Es una demostración, no un
dispositivo médico.
