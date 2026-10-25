class ErrorAteneoML(Exception):
    """Base de los errores del paquete."""


class ImagenIlegible(ErrorAteneoML):
    """Los bytes no se pudieron decodificar como imagen."""


class ModeloIncompatible(ErrorAteneoML):
    """El grafo ONNX no coincide con lo que declara el contrato."""
