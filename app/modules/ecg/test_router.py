import json
import math
import re
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
    assert datos["frecuencia_muestreo_hz"] == 250
    assert len(datos["muestras"]) == 2500
    assert all(math.isfinite(muestra) for muestra in datos["muestras"])


def _indices_picos_sinteticos(muestras):
    return [
        indice
        for indice in range(1, len(muestras) - 1)
        if muestras[indice] >= 0.8
        and muestras[indice] >= muestras[indice - 1]
        and muestras[indice] >= muestras[indice + 1]
    ]


def test_simulador_permite_configurar_frecuencia_y_duracion():
    datos = generar_datos_ecg(frecuencia_cardiaca_bpm=60, duracion_segundos=5)
    picos = _indices_picos_sinteticos(datos["muestras"])

    assert len(datos["muestras"]) == 1250
    assert DatosECG.model_validate(datos).frecuencia_muestreo_hz == 250
    assert len(picos) >= 4
    assert [right - left for left, right in zip(picos, picos[1:])] == [250] * (len(picos) - 1)


def test_senal_muy_corta_solo_se_valida_como_formato_tecnico():
    datos = generar_datos_ecg(duracion_segundos=0.004)

    assert len(datos["muestras"]) == 1
    assert DatosECG.model_validate(datos).muestras == datos["muestras"]


def test_simulador_genera_intervalos_regulares_e_irregulares_reproducibles():
    regular = generar_datos_ecg(ritmo="regular")
    irregular = generar_datos_ecg(ritmo="irregular", semilla=17)
    irregular_repetido = generar_datos_ecg(ritmo="irregular", semilla=17)
    rr_regular = [
        right - left
        for left, right in zip(
            _indices_picos_sinteticos(regular["muestras"]),
            _indices_picos_sinteticos(regular["muestras"])[1:],
        )
    ]
    picos_irregulares = _indices_picos_sinteticos(irregular["muestras"])
    rr_irregular = [right - left for left, right in zip(picos_irregulares, picos_irregulares[1:])]

    assert irregular == irregular_repetido
    assert len(set(rr_regular)) == 1
    assert len(set(rr_irregular)) > 1
    assert max(rr_irregular) - min(rr_irregular) >= 20


def test_simulador_admite_ruido_artefacto_y_onda_p_no_visible_solo_como_datos():
    limpia = generar_datos_ecg()
    ruidosa = generar_datos_ecg(ruido_amplitud=0.02, semilla=9)
    artefacto = generar_datos_ecg(artefacto_sintetico=True)
    sin_onda_p = generar_datos_ecg(onda_p_visible=False)

    assert ruidosa == generar_datos_ecg(ruido_amplitud=0.02, semilla=9)
    assert ruidosa["muestras"] != generar_datos_ecg(ruido_amplitud=0.02, semilla=10)["muestras"]
    assert artefacto["muestras"] != limpia["muestras"]
    assert sin_onda_p["muestras"] != limpia["muestras"]
    for datos in (ruidosa, artefacto, sin_onda_p):
        assert DatosECG.model_validate(datos)
        assert all(math.isfinite(muestra) for muestra in datos["muestras"])


@pytest.mark.parametrize(
    "parametros",
    [
        {"frecuencia_cardiaca_bpm": 0},
        {"frecuencia_cardiaca_bpm": 75.5},
        {"duracion_segundos": 0},
        {"duracion_segundos": float("nan")},
        {"ritmo": "sinusoidal"},
        {"ruido_amplitud": -0.1},
        {"ruido_amplitud": float("inf")},
        {"semilla": 1.5},
    ],
)
def test_simulador_rechaza_parametros_invalidos(parametros):
    with pytest.raises(ValueError):
        generar_datos_ecg(**parametros)


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


def test_entrada_ecg_usa_solo_los_campos_del_contrato():
    assert set(EntradaECG.model_fields) == {
        "episodio_id",
        "dispositivo_id",
        "origen",
        "data",
    }


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


def test_post_episodio_inexistente_devuelve_404_sin_persistir(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada["episodio_id"] = 999999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404
    assert response.json()["detail"] == "El episodio no existe"
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


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
    campo_id, ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada[campo_id] = 999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


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
    assert response.headers["cache-control"] == "no-store"
    assert "Recorrido educativo de captura ECG" in response.text
    assert "/api/v1/ecg/frontend.js" in response.text


def test_pantalla_ecg_delimita_contextos_hu09_y_hu14(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text

    assert "no se recibió una clasificación roja válida" in html
    assert "no se recibió un episodio del circuito completo" in html
    assert "esta pantalla no declara que el flujo HU-09 esté habilitado" in html


def test_pantalla_transversal_no_solicita_paciente_sin_contexto(ecg_client):
    html_response = ecg_client.get("/api/v1/ecg/circuito/pantalla")
    js_response = ecg_client.get("/api/v1/ecg/circuito/frontend.js")

    assert html_response.status_code == 200
    assert js_response.status_code == 200
    assert html_response.headers["cache-control"] == "no-store"
    assert 'name="tipo_circuito" value="GUARDIA"' in html_response.text
    assert 'name="tipo_circuito" value="COMPLETO"' in html_response.text
    assert 'id="paciente-id-entrada"' not in html_response.text
    assert 'id="crear-episodio" type="button" disabled' in html_response.text
    assert "no define un mecanismo para compartirlo entre pantallas" in html_response.text
    assert "No se selecciona ningún paciente automáticamente." in js_response.text
    assert 'radio.addEventListener("change"' in js_response.text
    html_ids = re.findall(r'\bid="([^"]+)"', html_response.text)
    selectors = re.findall(r'app\.querySelector\("#([^\"]+)"\)', js_response.text)
    assert len(html_ids) == len(set(html_ids))
    assert set(selectors) <= set(html_ids)


def test_pantalla_temporal_prueba_hu03_y_ecg(client):
    page = client.get("/api/v1/ecg/circuito/prueba")
    script = client.get("/api/v1/ecg/circuito/frontend.js")

    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert page.headers["cache-control"] == "no-store"
    assert "Herramienta temporal de prueba" in page.text
    assert 'data-mode="prueba"' in page.text
    assert 'src="/api/v1/ecg/circuito/frontend.js"' in page.text
    assert 'value="">Cargando pacientes…' in page.text
    assert 'name="tipo_circuito" value="GUARDIA"' in page.text
    assert 'name="tipo_circuito" value="COMPLETO"' in page.text
    assert script.status_code == 200
    assert 'API + "/pacientes"' in script.text
    assert 'new Option("Seleccioná un paciente existente…", "")' in script.text
    assert 'API + "/episodios"' in script.text
    assert 'API + "/episodios/" + created.id' in script.text
    assert "checked.paciente_id !== patient.id" in script.text
    assert 'root.querySelector("#seccion-ecg-prueba").hidden = false' in script.text
    assert 'API + "/dispositivos"' in script.text
    assert 'API + "/ecg/simulador/captura"' in script.text
    assert 'API + "/ecg/resultados"' in script.text
    assert 'API + "/ecg/resultados/" + episode.id' in script.text
    assert "localStorage" not in script.text
    assert "sessionStorage" not in script.text
    assert "URLSearchParams" not in script.text


def test_api_pacientes_devuelve_registros_reales_para_modo_prueba(client):
    created = client.post(
        "/api/v1/pacientes",
        json={
            "dni": "30987654",
            "nombre": "Paciente",
            "apellido": "Prueba temporal",
            "fecha_nacimiento": "1990-04-12",
        },
    )
    assert created.status_code == 201

    response = client.get("/api/v1/pacientes")

    assert response.status_code == 200
    patient = next(item for item in response.json() if item["id"] == created.json()["id"])
    assert patient["nombre"] == "Paciente"
    assert patient["apellido"] == "Prueba temporal"
    assert patient["dni"] == "30987654"


def test_pantallas_y_javascript_ecg_accesibles_desde_app_principal(client):
    pantalla_ecg = client.get("/api/v1/ecg/pantalla")
    pantalla_circuito = client.get("/api/v1/ecg/circuito/pantalla")
    javascript_ecg = client.get("/api/v1/ecg/frontend.js")
    javascript_circuito = client.get("/api/v1/ecg/circuito/frontend.js")

    assert pantalla_ecg.status_code == 200
    assert "text/html" in pantalla_ecg.headers["content-type"]
    assert 'src="/api/v1/ecg/frontend.js"' in pantalla_ecg.text
    assert pantalla_circuito.status_code == 200
    assert "text/html" in pantalla_circuito.headers["content-type"]
    assert 'src="/api/v1/ecg/circuito/frontend.js"' in pantalla_circuito.text
    assert javascript_ecg.status_code == 200
    assert "javascript" in javascript_ecg.headers["content-type"]
    assert javascript_circuito.status_code == 200
    assert "javascript" in javascript_circuito.headers["content-type"]


@pytest.mark.parametrize("tipo_circuito", ["GUARDIA", "COMPLETO"])
def test_app_principal_crea_episodio_con_circuito_admitido(
    client, test_engine, tipo_circuito
):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="12345678",
            nombre="Paciente",
            apellido="Prueba",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        paciente_id = paciente.id

    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": tipo_circuito},
    )

    assert response.status_code == 201
    assert response.json()["tipo_circuito"] == tipo_circuito
    assert response.json()["paciente_id"] == paciente_id


@pytest.mark.parametrize(
    "tipo_circuito",
    ["", "DESCONOCIDO", "TRIAJE_PREVENTIVO"],
)
def test_app_principal_rechaza_circuito_no_admitido_sin_crear_episodio(
    client, test_engine, tipo_circuito
):
    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": 1, "tipo_circuito": tipo_circuito},
    )

    assert response.status_code == 422
    with Session(test_engine) as session:
        assert session.exec(select(EpisodioAtencion)).all() == []


def test_app_principal_rechaza_paciente_inexistente(client, test_engine):
    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": 999999, "tipo_circuito": "COMPLETO"},
    )

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(EpisodioAtencion)).all() == []


@pytest.mark.parametrize("tipo_circuito", ["GUARDIA", "COMPLETO"])
def test_app_principal_persiste_y_consulta_ecg_simulado(
    client, test_engine, tipo_circuito
):
    patient_created = client.post(
        "/api/v1/pacientes",
        json={
            "dni": "87654321",
            "nombre": "Paciente",
            "apellido": "Prueba ECG",
            "fecha_nacimiento": "2000-01-01",
        },
    )
    assert patient_created.status_code == 201
    patient_list = client.get("/api/v1/pacientes")
    assert patient_list.status_code == 200
    paciente_id = patient_created.json()["id"]
    patient = next(item for item in patient_list.json() if item["id"] == paciente_id)
    assert patient["dni"] == "87654321"

    episodio_response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": tipo_circuito},
    )
    assert episodio_response.status_code == 201
    episodio_id = episodio_response.json()["id"]
    episode_check = client.get(f"/api/v1/episodios/{episodio_id}")
    assert episode_check.status_code == 200
    assert episode_check.json()["paciente_id"] == paciente_id
    assert episode_check.json()["tipo_circuito"] == tipo_circuito

    dispositivo_response = client.post(
        "/api/v1/dispositivos",
        json={"codigo": "001", "nombre": "ECG de prueba", "tipo": "ECG"},
    )
    assert dispositivo_response.status_code == 201
    dispositivos = client.get("/api/v1/dispositivos")
    assert dispositivos.status_code == 200
    dispositivo = next(item for item in dispositivos.json() if item["codigo"] == "001")
    assert dispositivo["tipo"] == "ECG"
    assert dispositivo["activo"] is True
    assert dispositivo["estado"] == "DISPONIBLE"

    captura = client.get("/api/v1/ecg/simulador/captura").json()
    entrada = {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo["id"],
        "origen": "SIMULADOR",
        "data": captura,
    }
    guardado = client.post("/api/v1/ecg/resultados", json=entrada)

    assert guardado.status_code == 201
    resultado_id = guardado.json()["resultado_id"]
    consulta = client.get(f"/api/v1/ecg/resultados/{episodio_id}")
    assert consulta.status_code == 200
    resultado = next(
        item for item in consulta.json()["resultados"] if item["id"] == resultado_id
    )
    assert consulta.json()["episodio_id"] == episodio_id
    assert resultado["data"] == captura

    with Session(test_engine) as session:
        persistido = session.exec(select(ResultadoModulo)).one()
    assert persistido.modulo == "ecg"
    assert persistido.episodio_id == episodio_id
    assert persistido.dispositivo_id == dispositivo["id"]
    assert json.loads(persistido.data_json) == captura


@pytest.mark.parametrize("campo_id", ["episodio_id", "dispositivo_id"])
def test_app_principal_no_persiste_resultado_con_referencia_inexistente(
    client, test_engine, campo_id
):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="11223344",
            nombre="Paciente",
            apellido="Prueba error",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        paciente_id = paciente.id

    episodio = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": "COMPLETO"},
    ).json()
    dispositivo = client.post(
        "/api/v1/dispositivos",
        json={"codigo": "001", "nombre": "ECG de prueba", "tipo": "ECG"},
    ).json()
    entrada = {
        "episodio_id": episodio["id"],
        "dispositivo_id": dispositivo["id"],
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    entrada[campo_id] = 999999

    response = client.post("/api/v1/ecg/resultados", json=entrada)

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_frontend_ecg_prepara_persistencia_con_contexto_real(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    response = ecg_client.get("/api/v1/ecg/frontend.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "/ecg/simulador/captura" in response.text
    assert "new URLSearchParams(window.location.search)" in response.text
    assert "${API}/episodios/${episodioId}" in response.text
    assert "${API}/dispositivos" in response.text
    assert 'device.codigo === "001"' in response.text
    assert 'device.tipo === "ECG"' in response.text
    assert "device.activo === true" in response.text
    assert 'origen: "SIMULADOR"' in response.text
    assert 'method: "POST"' in response.text
    assert "${API}/ecg/resultados/${episodioActivo.id}" in response.text
    assert '<section id="persistencia-panel"' in html
    assert '<button id="guardar-resultado" type="button" disabled>' in html
    assert 'saveButton.hidden = false' in response.text
    assert 'saveButton.disabled = !(hasEpisode && dispositivoEcg && capture' in response.text
    assert "paciente_id" not in response.text
    assert "no se declara completado el flujo rojo HU-09" in response.text
    assert "Prueba técnica HU-14" in response.text
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text


def test_frontend_ecg_reconcilia_error_antes_de_habilitar_reintento(ecg_client):
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    assert "async function reconcileUnconfirmedSave(error)" in javascript
    assert "await obtenerResultadosPersistidos()" in javascript
    assert "const match = results.find((result) => sameCapture(result.data, capture))" in javascript
    assert "canSubmitCapture = false" in javascript
    assert "canSubmitCapture = true" in javascript
    assert "if (!episodioActivo || !Number.isSafeInteger(episodioActivo.id) || episodioActivo.id <= 0" in javascript
    assert "paciente_id" not in javascript


def test_herramienta_temporal_muestra_estado_y_requisitos_del_guardado(ecg_client):
    html = ecg_client.get("/api/v1/ecg/circuito/prueba").text
    javascript = ecg_client.get("/api/v1/ecg/circuito/frontend.js").text

    assert '<button id="guardar-ecg-prueba" type="button" hidden disabled>' in html
    assert 'id="disponibilidad-guardado-prueba"' in html
    assert 'saveButton.addEventListener("click", saveCapture)' in javascript
    assert 'item.tipo === "ECG"' in javascript
    assert 'item.estado === "DISPONIBLE"' in javascript
    assert 'item.activo === true' in javascript
    assert 'Number.isSafeInteger(item.id) && item.id > 0' in javascript
    assert 'item.codigo === "001"' in javascript
    assert 'dispositivo_id: device.id' in javascript
    assert "No se encontró un dispositivo ECG activo y disponible" in javascript
    assert "falta un episodio verificado" in javascript
    assert "falta un dispositivo ECG activo y disponible" in javascript
    assert "falta generar la señal simulada" in javascript
    assert "Consultando resultados existentes antes de enviar la captura" in javascript
    assert 'API + "/ecg/resultados"' in javascript
    assert 'API + "/ecg/resultados/" + episode.id' in javascript
    assert "Guardado confirmado y verificado por la API" in javascript
    assert "paciente_id: episode.paciente_id" not in javascript


def test_captura_simulada_reutiliza_esquema_ecg(ecg_client):
    response = ecg_client.get("/api/v1/ecg/simulador/captura")

    assert response.status_code == 200
    assert DatosECG.model_validate(response.json()).model_dump() == generar_datos_ecg()



def test_pantalla_ecg_mantiene_la_secuencia_de_navegacion(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    step_ids = ["paso-preparacion", "paso-electrodos", "paso-captura", "paso-resumen"]
    assert [html.index(f'id="{step_id}"') for step_id in step_ids] == sorted(
        html.index(f'id="{step_id}"') for step_id in step_ids
    )
    html_ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(html_ids) == len(set(html_ids))
    selectors = re.findall(r'app\.querySelector\("#([^"]+)"\)', javascript)
    assert set(selectors) <= set(html_ids)
    assert html.count('id="paso-siguiente"') == 1
    assert all(f'#{step_id}' in javascript for step_id in step_ids)
    assert javascript.count('app.querySelector("#paso-siguiente").addEventListener("click"') == 1
    assert "showStep(currentStep + 1)" in javascript
    assert 'app.querySelector("#repetir-ecg").addEventListener("click", startSimulation)' in javascript
    assert 'app.querySelector("#finalizar-ecg").addEventListener("click", finishCaptureFlow)' in javascript
    assert 'app.querySelector("#finalizar-simulacion").addEventListener("click", finishCaptureFlow)' in javascript
    assert 'id="paso-guardar"' not in html
    assert 'id="paciente-seleccionado"' not in html
    assert 'id="paso-siguiente"' in html
    assert '<dl id="resumen-tecnico"' in html
    assert 'id="cantidad-final"' in html
    assert 'id="frecuencia-final"' in html
    assert 'id="unidad-final"' in html
    assert 'app.querySelector("#cantidad-final").textContent = String(capture.muestras.length)' in javascript
    assert 'app.querySelector("#frecuencia-final").textContent = `${capture.frecuencia_muestreo_hz} Hz`' in javascript
    assert 'app.querySelector("#unidad-final").textContent = capture.unidad' in javascript
    assert "muestras: shown" in javascript
    assert "${API}/ecg/resultados" in javascript
    assert "origen: \"SIMULADOR\"" in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert "No se guardó ningún resultado." in html
    assert 'src="/api/v1/ecg/frontend.js"' in html
