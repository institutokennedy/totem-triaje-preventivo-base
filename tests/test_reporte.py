from types import SimpleNamespace

from app.reporte.reporte import construir_reporte, render_html


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


def test_reporte_incluye_diagrama_de_audiometria():
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
                        "frecuencias_hz": [250, 500, 1000, 2000, 4000, 8000],
                        "resultados_oido_derecho": [True, True, False, False, False, False],
                        "resultados_oido_izquierdo": [False, True, True, False, False, True],
                    }
                }
            ]
        },
        [],
    )

    assert "audiometria" in reporte
    assert reporte["audiometria"]["frecuencias_hz"] == [250, 500, 1000, 2000, 4000, 8000]
    assert len(reporte["audiometria"]["derecho"]) == 6
    assert len(reporte["audiometria"]["izquierdo"]) == 6

    html = render_html(reporte)
    assert "Oído derecho" in html
    assert "Oído izquierdo" in html
    assert "Se escucha" in html
    assert "No se escucha" in html


def test_reporte_incluye_formulario_del_oido_al_final():
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
                        "cuestionario": {
                            "tiene_problema_auditivo": True,
                            "problemas_auditivos": ["hipoacusia", "misofonia"],
                            "otro_problema": "Mareo",
                            "factores": ["diabetes", "exposicion_ruidos_fuertes"],
                        }
                    }
                }
            ]
        },
        [],
    )

    assert "cuestionario" in reporte
    assert reporte["cuestionario"]["tiene_problema_auditivo"] is True
    html = render_html(reporte)
    assert "Formulario" in html
    assert "¿Presenta algún problema o inconveniente de audición?" in html
    assert "Hipoacusia" in html
    assert "Diabetes" in html


def test_reporte_no_marca_como_escucha_si_responde_lado_equivocado():
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
                                "frecuencia_hz": 1000,
                                "lado_estimulo": "DERECHO",
                                "respuesta": "IZQUIERDO",
                            }
                        ]
                    }
                }
            ]
        },
        [],
    )

    assert reporte["audiometria"]["derecho"][0]["escucha"] is False
    assert reporte["audiometria"]["izquierdo"][0]["escucha"] is False
