# CNN · Tumor cerebral

Pesos preentrenados de NareshKumarSekar, publicados con su Space:
https://huggingface.co/spaces/NareshKumarSekar/BrainTumor.
Revisión `0323f6ee650bfa2b0ef5d3352e15971ea0d6c5e3`, archivo `brain_tumor_model.onnx`.
El Space declara MIT; se conserva la atribución al autor. Los pesos no se
redistribuyen en Git: se descargan y verifican con el manifiesto.

Clasifica cortes de RM cerebral en cuatro clases. Es una red convolucional propia
del autor, no una arquitectura conocida: 6 convoluciones, exportada de Keras con
tf2onnx. Entrada RGB float32 NHWC 224 × 224, dividida por 255 y sin otra
normalización; salida `output_0`, ya pasada por softmax adentro del grafo. Así
lo hace la función `classify_tumor` del `app.py` del Space.

El `app.py` nombra las salidas `Glioma`, `Meningioma`, `No Tumor` y `Pituitary`.
El contrato conserva ese orden con el vocabulario del conjunto reservado
(`glioma`, `meningioma`, `notumor`, `pituitary`).

El Space no dice con qué datos se entrenó. Si fue con el train del dataset de
Kaggle, hereda su fuga con el test y las métricas de Ateneo son algo optimistas.
Es una demostración, no un dispositivo médico.
