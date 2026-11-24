from datetime import date, datetime
import re
from types import SimpleNamespace
from xml.etree import ElementTree

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

    assert reporte["resultados_auditivos"] == {
        "frecuencias_hz": [500, 1000, 2000],
        "resultados_oido_derecho": [None, True, None],
        "resultados_oido_izquierdo": [True, None, False],
        "origen": None,
    }
    mediciones = dict(reporte["mediciones"])
    assert mediciones["Respuesta oído derecho"] == "500 Hz: Sin respuesta; 1000 Hz: Sí; 2000 Hz: Sin respuesta"
    assert mediciones["Respuesta oído izquierdo"] == "500 Hz: Sí; 1000 Hz: Sin respuesta; 2000 Hz: No"
    assert "Origen registrado" not in mediciones
    html = render_html(reporte)
    assert "ensayos" not in html.lower()
    assert mediciones["Respuesta oído derecho"] in html
    assert mediciones["Respuesta oído izquierdo"] in html


def test_reporte_muestra_datos_registrados_y_modulos_pendientes():
    paciente = SimpleNamespace(
        nombre="Paciente",
        apellido="Ficticio",
        fecha_nacimiento=None,
        email=None,
    )
    reporte = construir_reporte(
        paciente,
        {
            "signos_vitales": [
                {
                    "data": {
                        "presion_sistolica": 118.0,
                        "presion_diastolica": 76.0,
                        "frecuencia_cardiaca": 74.0,
                        "temperatura": 36.5,
                        "saturacion_oxigeno": 98.0,
                    }
                }
            ],
            "ecg": [
                {
                    "data": {
                        "frecuencia_muestreo_hz": 250,
                        "muestras": [0.02, 0.08, 0.31],
                        "unidad": "mV",
                    }
                }
            ],
        },
        [],
    )

    assert reporte["mediciones"] == []
    grupos = {
        modulo["modulo"]: modulo
        for modulo in reporte["resultados_por_modulo"]
    }
    assert grupos["signos_vitales"]["tiene_datos"] is True
    assert grupos["signos_vitales"]["detalles"][0] == {
        "campo": "presion_sistolica",
        "etiqueta": "Presión sistólica",
        "valor": 118.0,
        "valor_formateado": "118.0",
    }
    assert grupos["ecg"]["tiene_datos"] is True
    assert grupos["ecg"]["detalles"][1]["valor_formateado"] == "0.02, 0.08, 0.31"
    assert grupos["glucemia"]["estado"] == "Sin datos obtenidos"
    assert grupos["boca"]["estado"] == "Sin datos obtenidos"
    assert grupos["vista"]["estado"] == "Sin datos obtenidos"
    assert grupos["oido"]["estado"] == "Sin datos obtenidos"

    html = render_html(reporte)
    for titulo in (
        "Grupo 1 · Signos vitales",
        "Grupo 2 · ECG",
        "Grupo 3 · Glucemia",
        "Grupo 4 · Boca",
        "Grupo 5 · Vista",
        "Grupo 6 · Oído",
    ):
        assert titulo in html
    assert "118.0" in html
    assert "0.31" in html
    assert html.count("Sin datos registrados") >= 9
    assert html.count("Sin datos obtenidos") == 4


def test_reporte_usa_los_datos_personales_registrados_del_paciente():
    paciente = SimpleNamespace(
        nombre="Ana",
        apellido="García",
        dni="30123456",
        fecha_nacimiento=date(2000, 5, 6),
        email="ana@example.test",
        telefono="3515551234",
    )

    reporte = construir_reporte(
        paciente, {}, [], ahora=datetime(2026, 11, 3, 10, 15)
    )

    datos_personales = dict(reporte["paciente"])
    assert datos_personales["Nombre Completo"] == "Ana García"
    assert datos_personales["DNI"] == "30123456"
    assert datos_personales["Fecha de nacimiento"] == "06/05/2000"
    assert datos_personales["Fecha/Hora"] == "03/11/2026 10:15"
    assert datos_personales["Correo"] == "ana@example.test"
    assert datos_personales["Teléfono"] == "3515551234"

    html = render_html(reporte)
    for dato in ("Ana García", "30123456", "06/05/2000", "ana@example.test", "3515551234"):
        assert dato in html


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
    assert reporte["resultados_auditivos"]["resultados_oido_derecho"] == [
        True, True, False, False, False, False
    ]
    assert reporte["resultados_auditivos"]["resultados_oido_izquierdo"] == [
        False, True, True, False, False, True
    ]

    html = render_html(reporte)
    assert "Oído derecho" in html
    assert "Oído izquierdo" in html
    assert "Percibido" in html
    assert "No percibido" in html
    assert "no representa umbrales en db hl" in html.lower()
    assert "Límite normal (20 dB)" not in html
    assert html.count("Detalle por frecuencia") == 2
    assert html.count("Se escucha") == 2
    assert html.count("No se escucha") == 2
    assert html.count("audicion-frecuencia si") == 5
    assert html.count("audicion-frecuencia no") == 7
    assert "250 Hz" in html
    assert "Resultados reales registrados · Audiometría" in html
    assert html.count("Grupo 6 · Oído") == 1
    assert "Origen registrado" not in html
    assert html.index("Grupo 6 · Oído") < html.index("Resultados reales registrados · Audiometría")
    assert html.index("Resultados reales registrados · Audiometría") < html.index("Resultado preventivo general")
    assert "Frecuencia Cardíaca" not in html
    assert "Presión Arterial" not in html
    etiquetas_medicion = {etiqueta for etiqueta, _ in reporte["mediciones"]}
    assert etiquetas_medicion == {
        "Frecuencias evaluadas",
        "Respuesta oído derecho",
        "Respuesta oído izquierdo",
    }
    for svg in re.findall(r"<svg\b.*?</svg>", html, flags=re.DOTALL):
        ElementTree.fromstring(svg)


def test_reporte_incluye_formulario_en_la_seccion_de_oido():
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
    assert "Exposición a ruidos fuertes" in html
    assert "Problemas auditivos marcados" not in html
    assert html.count("Problemas auditivos</div>") == 1
    assert "Antecedentes y factores marcados" in html
    assert html.count("Formulario") == 1
    assert html.count("Grupo 6 · Oído") == 1
    assert html.index("Grupo 6 · Oído") < html.index("Formulario")
    form_index = html.index('<div class="formulario-oido">')
    hearing_panel_start = html.rfind('<section class="panel">', 0, form_index)
    hearing_panel_end = html.index("</section>", form_index)
    assert html.index("Grupo 6 · Oído") > hearing_panel_start
    assert hearing_panel_end > form_index
    assert html.index("Formulario") < html.index("Resultado preventivo general")
    assert html.index("Resultado preventivo general") < html.index("Observaciones / alertas")


def test_reporte_muestra_respuesta_negativa_aunque_no_haya_factores_marcados():
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
                            "tiene_problema_auditivo": False,
                            "problemas_auditivos": [],
                            "otro_problema": "",
                            "factores": [],
                        }
                    }
                }
            ]
        },
        [],
    )

    html = render_html(reporte)
    assert "Formulario" in html
    assert '<span class="metric-value">No</span>' in html
    assert "No se registraron factores asociados." in html


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

    assert reporte["audiometria"]["derecho"][0]["respuesta"] == "LADO_OPUESTO"
    assert reporte["audiometria"]["izquierdo"][0]["respuesta"] is None
    assert reporte["resultados_auditivos"]["resultados_oido_derecho"] == [True]


def test_diagrama_muestra_localizacion_correcta_y_no_escuche_por_frecuencia():
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
                                "respuesta": "DERECHO",
                            },
                            {
                                "frecuencia_hz": 1000,
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

    audiometria = reporte["audiometria"]
    assert audiometria["derecho"][0]["respuesta"] == "CORRECTA"
    assert audiometria["izquierdo"][0]["respuesta"] == "NO_ESCUCHE"
    assert "db" not in audiometria["derecho"][0]
    html = render_html(reporte)
    assert "Lado correcto" in html
    assert "No escuchó" in html
    assert html.count("audicion-frecuencia si") == 1
    assert html.count("audicion-frecuencia no") == 1
    assert "Sin resp.</div>" not in html
    assert html.index("Detalle por frecuencia") < html.index("Resultado preventivo general")
    assert html.index("Resultado preventivo general") < html.index("Observaciones / alertas")
