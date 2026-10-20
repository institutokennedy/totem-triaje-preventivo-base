def test_paginas_de_oido_y_resumen(client):
    pagina_oido = client.get("/oido?episodio_id=1")
    pagina_resumen = client.get("/resumen?episodio_id=1")

    assert pagina_oido.status_code == 200
    assert "Evaluación auditiva" in pagina_oido.text
    assert pagina_resumen.status_code == 200
    assert "Resumen del episodio" in pagina_resumen.text


def test_estado_de_integracion_ia_no_revela_la_clave(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    desactivada = client.get("/api/v1/analisis-ia/estado")
    assert desactivada.status_code == 200
    assert desactivada.json()["habilitada"] is False

    monkeypatch.setenv("GEMINI_API_KEY", "secreto-de-prueba")
    monkeypatch.setenv("GEMINI_MODEL", "modelo-prueba")

    respuesta = client.get("/api/v1/analisis-ia/estado")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "habilitada": True,
        "modelo": "modelo-prueba",
        "motivo": "",
    }
    assert "secreto-de-prueba" not in respuesta.text


def test_resultado_oido_se_incluye_en_informe(client, demo_references, monkeypatch):
    from app.modules.informes import analisis_ia

    entrada_ia = {}

    def sin_analisis(*, edad, por_modulo, pendientes):
        entrada_ia.update(
            analisis_ia.construir_entrada(
                edad=edad,
                por_modulo=por_modulo,
                pendientes=pendientes,
            )
        )
        return None, "GEMINI_API_KEY no configurada"

    monkeypatch.setattr(
        analisis_ia,
        "analizar_resultados",
        sin_analisis,
    )
    episodio_id = demo_references["episodio_id"]
    payload = {
        "episodio_id": episodio_id,
        "dispositivo_id": demo_references["dispositivo_id"],
        "origen": "SIMULADOR",
        "data": {
            "frecuencias_hz": [500, 1000],
            "resultados_oido_derecho": [True, False],
            "resultados_oido_izquierdo": [True, True],
            "nivel_senal": "REDUCIDO_POR_AUTOINFORME",
            "cuestionario": {
                "tiene_problema_auditivo": True,
                "problemas_auditivos": ["hipoacusia"],
                "otro_problema": "",
                "factores": ["otitis_frecuentes"],
            },
        },
    }

    resultado = client.post("/api/v1/oido/resultados", json=payload)
    assert resultado.status_code == 201
    assert resultado.json()["origen"] == "SIMULADOR"
    assert "_origen" not in resultado.json()["data_json"]

    informe_response = client.post(
        f"/api/v1/episodios/{episodio_id}/informes"
    )
    assert informe_response.status_code == 201
    informe = informe_response.json()
    registro_oido = informe["contenido"]["resultados"]["oido"][0]
    assert registro_oido["origen"] == "SIMULADOR"
    assert registro_oido["data"]["resultados_oido_derecho"] == [True, False]
    assert registro_oido["data"]["nivel_senal"] == "REDUCIDO_POR_AUTOINFORME"
    assert registro_oido["data"]["cuestionario"]["problemas_auditivos"] == [
        "hipoacusia"
    ]
    assert entrada_ia["edad_anios"] == 26
    assert entrada_ia["modulos"]["oido"]["resultados_oido_derecho"] == [
        True,
        False,
    ]
    assert entrada_ia["modulos"]["oido"]["nivel_senal"] == "REDUCIDO_POR_AUTOINFORME"
    assert entrada_ia["modulos"]["oido"]["cuestionario"] == {
        "tiene_problema_auditivo": True,
        "problemas_auditivos": ["hipoacusia"],
        "factores": ["otitis_frecuentes"],
    }

    pagina_informe = client.get(
        f"/api/v1/episodios/{episodio_id}/informes/{informe['id']}/html"
    )
    assert pagina_informe.status_code == 200
    assert "Informe preventivo. No constituye un diagnóstico médico." in pagina_informe.text
    assert "Análisis orientativo asistido por IA" in pagina_informe.text
    assert "No disponible" in pagina_informe.text
    assert "Reducido por autoinforme" in pagina_informe.text


def test_informe_incluye_analisis_ia_como_orientativo(
    client, demo_references, monkeypatch
):
    from app.modules.informes import analisis_ia

    analisis = {
        "estado": "AMARILLO",
        "resumen": "Hallazgos para revisar <script>alert(1)</script>.",
        "motivos": ["Requiere revisión."],
        "subindices": {"auditivo": "AMARILLO"},
        "alertas": [],
        "recomendacion": "Consulta profesional.",
        "modelo": "modelo-prueba",
    }
    monkeypatch.setattr(
        analisis_ia, "analizar_resultados", lambda **kwargs: (analisis, None)
    )
    episodio_id = demo_references["episodio_id"]
    respuesta = client.post(f"/api/v1/episodios/{episodio_id}/informes")

    assert respuesta.status_code == 201
    informe = respuesta.json()
    contenido = informe["contenido"]
    assert contenido["analisis_ia"] == analisis
    assert contenido["analisis_ia_estado"] == {"disponible": True, "motivo": None}
    assert contenido["reporte"]["triaje"]["estado"] == "PENDIENTE"

    pagina = client.get(
        f"/api/v1/episodios/{episodio_id}/informes/{informe['id']}/html"
    )
    assert "Nivel sugerido (no validado):" in pagina.text
    assert "revisión profesional" in pagina.text
    assert "&lt;script&gt;" in pagina.text
    assert "<script>alert(1)</script>" not in pagina.text
