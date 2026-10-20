# Imagen `ml`: el worker (por defecto) y el evaluador (`python -m evaluador.main`), más las
# herramientas. Los dos servicios usan la misma imagen a propósito: la métrica certificada se
# calcula con el mismo preprocesamiento con el que después se infiere.
# Lleva ONNX Runtime y ateneo_ml; no tiene driver de base ni cómo hablar con ella.

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir onnxruntime==1.18.0 "numpy<2" pillow pydicom boto3==1.35.90
WORKDIR /opt/ml
COPY ateneo_ml ./ateneo_ml
COPY worker ./worker
COPY evaluador ./evaluador
COPY tools ./tools
RUN mkdir -p /mnt/modelos /opt/ml/tmp
CMD ["python", "-m", "worker.main"]
