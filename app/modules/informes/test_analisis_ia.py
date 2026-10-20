import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.modules.informes import analisis_ia
from app.modules.informes.analisis_ia import (
    analizar_resultados,
    construir_entrada,
    parsear_respuesta,
)

POR_MODULO = {
    "oido": [
        {
            "id": 1,
            "dispositivo_id": 1,
            "data": {
                "frecuencias_hz": [500, 1000, 2000],
                "resultados_oido_derecho": [True, False, False],
                "resultados_oido_izquierdo": [True, True, True],
                "nivel_senal": "REDUCIDO_POR_AUTOINFORME",
                "cuestionario": {"tiene_problema_auditivo": True, "factores": ["diabetes"]},
            },
        }
    ]
}

RESPUESTA_OK = {
    "estado": "amarillo",
    "resumen": "Hallazgos leves en el oído derecho.",
    "motivos": ["No percibió 1000 y 2000 Hz en el oído derecho."],
    "subindices": {"auditivo": "amarillo", "otro": "azul"},
    "alertas": [],
    "recomendacion": "Consultar a un profesional.",
}


def test_entrada_calcula_frecuencias_no_percibidas_y_no_incluye_datos_personales():
    entrada = construir_entrada(16, POR_MODULO, ["vision"])
    oido = entrada["modulos"]["oido"]
    assert oido["frecuencias_no_percibidas_derecho"] == [1000, 2000]
    assert oido["frecuencias_no_percibidas_izquierdo"] == []
    assert oido["nivel_senal"] == "REDUCIDO_POR_AUTOINFORME"
    assert oido["cuestionario"]["tiene_problema_auditivo"] is True
    assert oido["cuestionario"]["factores"] == ["diabetes"]
    assert entrada["edad_anios"] == 16
    assert entrada["modulos_pendientes"] == ["vision"]
    texto = json.dumps(entrada)
    for clave in ("nombre", "apellido", "dni", "correo", "email"):
        assert clave not in texto


def test_instrucciones_de_ia_usan_cuestionario_en_la_clasificacion():
    assert "Integra en la clasificación los síntomas y factores de riesgo" in analisis_ia.SYSTEM_PROMPT
    assert "no como diagnósticos confirmados" in analisis_ia.SYSTEM_PROMPT
    assert "automáticamente un nivel alto por una casilla aislada" in analisis_ia.SYSTEM_PROMPT


def test_entrada_filtra_datos_personales_y_notas_de_otros_modulos():
    por_modulo = {
        "signos_vitales": [
            {
                "data": {
                    "frecuencia_cardiaca": 72,
                    "paciente_id": 4,
                    "paciente": {"nombre": "Dato privado"},
                    "observaciones": "Texto libre",
                }
            }
        ]
    }

    entrada = construir_entrada(16, por_modulo, [])

    assert entrada["modulos"]["signos_vitales"] == {"frecuencia_cardiaca": 72}


def test_parsear_respuesta_valida_y_normaliza():
    r = parsear_respuesta(json.dumps(RESPUESTA_OK))
    assert r["estado"] == "AMARILLO"
    assert r["subindices"] == {"auditivo": "AMARILLO"}  # "azul" se descarta


def test_parsear_respuesta_con_bloque_de_codigo():
    texto = "```json\n" + json.dumps(RESPUESTA_OK) + "\n```"
    assert parsear_respuesta(texto)["estado"] == "AMARILLO"


@pytest.mark.parametrize(
    "texto",
    ["", "sin json", "{no es json}", json.dumps({**RESPUESTA_OK, "estado": "NARANJA"}), "[1, 2]"],
)
def test_parsear_respuesta_invalida(texto):
    assert parsear_respuesta(texto) is None


def test_sin_clave_no_se_analiza(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    analisis, motivo = analizar_resultados(16, POR_MODULO, [])
    assert analisis is None
    assert "GEMINI_API_KEY" in motivo


def test_estado_configuracion_indica_si_ia_esta_activa(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert analisis_ia.estado_configuracion()["habilitada"] is False

    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    assert analisis_ia.estado_configuracion()["habilitada"] is True
    assert analisis_ia.estado_configuracion()["modelo"] == "gemini-3.8-flash"


def test_llamar_modelo_usa_gemini_generate_content(monkeypatch):
    llamada = {}

    class FakeClient:
        def __init__(self, **kwargs):
            llamada["cliente"] = kwargs
            self.models = SimpleNamespace(generate_content=self.generar_contenido)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            llamada["cerrado"] = True

        @staticmethod
        def generar_contenido(**kwargs):
            llamada["solicitud"] = kwargs
            return SimpleNamespace(text='{"estado":"VERDE"}')

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs):
            self.options = kwargs

    class FakeHttpOptions:
        def __init__(self, **kwargs):
            self.options = kwargs

    fake_genai = ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_genai.types = SimpleNamespace(
        GenerateContentConfig=FakeGenerateContentConfig,
        HttpOptions=FakeHttpOptions,
    )
    fake_google = ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    respuesta = analisis_ia._llamar_modelo({"edad_anios": 16})

    assert respuesta == '{"estado":"VERDE"}'
    assert llamada["cliente"]["api_key"] == "clave-de-prueba"
    assert llamada["cliente"]["http_options"].options == {"timeout": 30000}
    assert llamada["solicitud"]["model"] == "gemini-3.8-flash"
    assert llamada["solicitud"]["contents"] == '{"edad_anios": 16}'
    assert llamada["solicitud"]["config"].options == {
        "system_instruction": analisis_ia.SYSTEM_PROMPT,
        "max_output_tokens": 1000,
        "response_mime_type": "application/json",
    }
    assert llamada["cerrado"] is True


def test_analisis_exitoso(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")
    monkeypatch.setattr(analisis_ia, "_llamar_modelo", lambda entrada: json.dumps(RESPUESTA_OK))
    analisis, motivo = analizar_resultados(16, POR_MODULO, [])
    assert motivo is None
    assert analisis["estado"] == "AMARILLO"
    assert analisis["modelo"]


def test_fallo_del_modelo_no_rompe(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")

    def falla(entrada):
        raise TimeoutError("sin red")

    monkeypatch.setattr(analisis_ia, "_llamar_modelo", falla)
    analisis, motivo = analizar_resultados(16, POR_MODULO, [])
    assert analisis is None and motivo == "TimeoutError"