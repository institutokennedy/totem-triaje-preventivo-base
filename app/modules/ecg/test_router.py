import json
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, select

from app.common.models import (
    Dispositivo,
    EpisodioAtencion,
    Paciente,
    ResultadoModulo,
)
from app.core.database import get_session
from app.modules.ecg.router import router as ecg_router
from app.modules.ecg.schemas import DatosECG, EntradaECG, RespuestaConsulta
from app.modules.ecg.simulator import generar_datos_ecg


RUTA = "/api/v1/ecg/resultados"


@pytest.fixture()
def ecg_app(test_engine):
    SQLModel.metadata.create_all(test_engine)
    application = FastAPI()
    application.include_router(ecg_router)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def ecg_client(ecg_app):
    with TestClient(ecg_app) as test_client:
        yield test_client


@pytest.fixture()
def ecg_references(test_engine, ecg_app):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="12345678",
            nombre="Paciente",
            apellido="Ficticio",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)

        episodio = EpisodioAtencion(
            paciente_id=paciente.id,
            tipo_circuito="COMPLETO",
        )
        dispositivo = Dispositivo(
            codigo="ECG-TEST-001",
            nombre="Simulador ECG ficticio",
            tipo="ECG",
        )
        session.add(episodio)
        session.add(dispositivo)
        session.commit()
        session.refresh(episodio)
        session.refresh(dispositivo)

        return {
            "episodio_id": episodio.id,
            "dispositivo_id": dispositivo.id,
        }


def _entrada_valida(references):
    return {
        "episodio_id": references["episodio_id"],
        "dispositivo_id": references["dispositivo_id"],
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }


def test_esquema_y_simulador_generan_datos_ecg_validos():
    datos = generar_datos_ecg()

    assert set(datos) == {
        "frecuencia_muestreo_hz",
        "muestras",
        "unidad",
    }
    assert DatosECG.model_validate(datos).model_dump() == datos
    assert generar_datos_ecg() == datos


@pytest.mark.parametrize(
    "datos",
    [
        {},
        {"frecuencia_muestreo_hz": 0, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": -1, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250.5, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": ["0.1"], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [float("nan")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [float("inf")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [-float("inf")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [0.1], "unidad": "V"},
    ],
)
def test_datos_ecg_rechaza_campos_y_valores_invalidos(datos):
    with pytest.raises(ValidationError):
        DatosECG.model_validate(datos)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("episodio_id", 0),
        ("episodio_id", -1),
        ("dispositivo_id", 0),
        ("dispositivo_id", -1),
    ],
)
def test_entrada_ecg_rechaza_identificadores_no_positivos(campo, valor):
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    entrada[campo] = valor

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


@pytest.mark.parametrize(
    "campo",
    ["episodio_id", "dispositivo_id", "origen", "data"],
)
def test_entrada_ecg_rechaza_campos_obligatorios_ausentes(campo):
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    del entrada[campo]

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


def test_entrada_ecg_rechaza_origen_invalido():
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "MANUAL",
        "data": generar_datos_ecg(),
    }

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


def test_guardar_resultado_valido(ecg_client, test_engine, ecg_references):
    entrada = _entrada_valida(ecg_references)

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 201
    respuesta = response.json()
    assert respuesta["mensaje"] == "Resultado guardado correctamente"
    assert isinstance(respuesta["resultado_id"], int)

    with Session(test_engine) as session:
        resultado = session.exec(select(ResultadoModulo)).one()

    assert resultado.id == respuesta["resultado_id"]
    assert resultado.modulo == "ecg"
    assert resultado.episodio_id == ecg_references["episodio_id"]
    assert resultado.dispositivo_id == ecg_references["dispositivo_id"]
    assert json.loads(resultado.data_json) == entrada["data"]


def test_post_rechaza_entrada_invalida_con_422(ecg_client, ecg_references):
    entrada = _entrada_valida(ecg_references)
    entrada["data"]["unidad"] = "V"

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "campo_id",
    ["episodio_id", "dispositivo_id"],
)
def test_post_referencia_inexistente_devuelve_404(
    campo_id, ecg_client, ecg_references
):
    entrada = _entrada_valida(ecg_references)
    entrada[campo_id] = 999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404


def test_get_resultados_del_episodio(ecg_client, ecg_references):
    entrada = _entrada_valida(ecg_references)
    guardado = ecg_client.post(RUTA, json=entrada)

    response = ecg_client.get(
        f"{RUTA}/{ecg_references['episodio_id']}"
    )

    assert guardado.status_code == 201
    assert response.status_code == 200
    respuesta = RespuestaConsulta.model_validate(response.json())
    assert respuesta.episodio_id == ecg_references["episodio_id"]
    assert respuesta.modulo == "ecg"
    assert len(respuesta.resultados) == 1
    assert respuesta.resultados[0].id == guardado.json()["resultado_id"]
    assert respuesta.resultados[0].data.model_dump() == entrada["data"]


def test_get_episodio_existente_sin_resultados_devuelve_lista_vacia(
    ecg_client, ecg_references
):
    response = ecg_client.get(
        f"{RUTA}/{ecg_references['episodio_id']}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "episodio_id": ecg_references["episodio_id"],
        "modulo": "ecg",
        "resultados": [],
    }


def test_get_episodio_inexistente_devuelve_404(ecg_client):
    response = ecg_client.get(f"{RUTA}/999")

    assert response.status_code == 404


@pytest.mark.parametrize("episodio_id", [0, -1])
def test_get_episodio_no_positivo_devuelve_422(ecg_client, episodio_id):
    response = ecg_client.get(f"{RUTA}/{episodio_id}")

    assert response.status_code == 422


def test_pantalla_ecg_disponible_desde_router_principal(ecg_client):
    response = ecg_client.get("/api/v1/ecg/pantalla")

    assert response.status_code == 200
    assert "Recorrido educativo de captura ECG" in response.text
    assert "/api/v1/ecg/frontend.js" in response.text


def test_frontend_ecg_disponible_desde_router_principal(ecg_client):
    response = ecg_client.get("/api/v1/ecg/frontend.js")

    assert response.status_code == 200
    assert "SIMULADOR" in response.text
    assert "/ecg/resultados" in response.text


def test_captura_simulada_reutiliza_esquema_ecg(ecg_client):
    response = ecg_client.get("/api/v1/ecg/simulador/captura")

    assert response.status_code == 200
    assert DatosECG.model_validate(response.json()).model_dump() == generar_datos_ecg()



def test_pantalla_ecg_puede_recorrerse_sin_episodio_inicial(ecg_client):
    response = ecg_client.get("/api/v1/ecg/pantalla")

    assert response.status_code == 200
    html = response.text
    preparacion = html.split('<section id="paso-preparacion"', 1)[1].split("</section>", 1)[0]
    assert "episodio-id" not in preparacion
    assert html.index('id="paso-preparacion"') < html.index('id="paso-electrodos"')
    assert html.index('id="paso-electrodos"') < html.index('id="paso-conexiones"')
    assert html.index('id="paso-conexiones"') < html.index('id="paso-captura"')
    assert html.index('id="paso-captura"') < html.index('id="paso-resumen"')
    assert html.index('id="paso-resumen"') < html.index('id="paso-guardar"')


