def generar_entrada_ficticia(episodio_id: int, dispositivo_id: int) -> dict:
    """Genera un ejemplo para copiar, revisar y confirmar en Swagger."""
    return {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo_id,
        "origen": "SIMULADOR",
        "data": {
            "temperatura_c": 24.5,
            "humedad_porcentaje": 45.0,
        },
    }
