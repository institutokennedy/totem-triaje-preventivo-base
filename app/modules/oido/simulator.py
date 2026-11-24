import random


def simular_evaluacion_auditiva(frecuencias_hz: list[int]) -> dict:
    """Genera respuestas booleanas ficticias (True = respuesta registrada al estímulo)
    para cada frecuencia y cada oído. No aplica umbrales ni interpretación clínica."""
    if not frecuencias_hz:
        raise ValueError("frecuencias_hz no puede estar vacía")
    if any((not isinstance(f, int)) or isinstance(f, bool) or f <= 0 for f in frecuencias_hz):
        raise ValueError("Las frecuencias deben ser enteros mayores a 0")

    return {
        "frecuencias_hz": list(frecuencias_hz),
        "resultados_oido_derecho": [random.choice([True, False]) for _ in frecuencias_hz],
        "resultados_oido_izquierdo": [random.choice([True, False]) for _ in frecuencias_hz],
    }