def generar_datos_ecg() -> dict[str, int | list[float] | str]:
    """Devuelve una captura ECG ficticia y determinista para demostración técnica.

    La frecuencia, unidad y muestras reutilizan el ejemplo del contrato API.
    """
    return {
        "frecuencia_muestreo_hz": 250,
        "muestras": [0.02, 0.08, 0.31, 0.12, -0.04],
        "unidad": "mV",
    }
