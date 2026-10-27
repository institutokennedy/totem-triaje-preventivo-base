from types import SimpleNamespace

from app.reporte.reporte import construir_reporte


def test_reporte_resume_answers_from_randomized_hearing_trials():
    paciente = SimpleNamespace(
        nombre="Paciente",
        apellido="Ficticio",
        fecha_nacimiento=None,
        email=None,
    )
    reporte = construir_reporte(
        paciente,
        {
            "oido": [
                {
                    "data": {
                        "ensayos": [
                            {
                                "frecuencia_hz": 500,
                                "lado_estimulo": "IZQUIERDO",
                                "respuesta": "DERECHO",
                            },
                            {
                                "frecuencia_hz": 1000,
                                "lado_estimulo": "DERECHO",
                                "respuesta": "IZQUIERDO",
                            },
                            {
                                "frecuencia_hz": 2000,
                                "lado_estimulo": "IZQUIERDO",
                                "respuesta": "NO_ESCUCHE",
                            },
                        ]
                    }
                }
            ]
        },
        [],
    )

    mediciones = dict(reporte["mediciones"])
    assert mediciones["Respuestas que indicaron derecha"] == (
        "1 respuesta señaló el lado derecho"
    )
    assert mediciones["Respuestas que indicaron izquierda"] == (
        "1 respuesta señaló el lado izquierdo"
    )
    assert mediciones["Tonos que la persona indicó no escuchar"] == "1"
