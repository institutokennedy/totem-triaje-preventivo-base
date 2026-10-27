import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def obtener_o_crear_recursos_prueba():
    """Crea o recupera paciente, episodio y dispositivo GLU-001 de prueba."""
    # 1. Registrar o recuperar paciente
    pac_res = client.post(
        "/api/v1/pacientes",
        json={
            "dni": "99988877",
            "nombre": "Prueba",
            "apellido": "Glucemia",
            "fecha_nacimiento": "2000-01-01",
        },
    )
    if pac_res.status_code == 201:
        paciente_id = pac_res.json()["id"]
    else:
        pacientes = client.get("/api/v1/pacientes").json()
        paciente_id = pacientes["id"]

    # 2. Crear o recuperar episodio
    ep_res = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": "COMPLETO"},
    )
    if ep_res.status_code == 201:
        episodio_id = ep_res.json()["id"]
    else:
        episodios = client.get("/api/v1/episodios").json()
        episodio_id = episodios["id"]

    # 3. Registrar o recuperar dispositivo GLU-001
    disp_res = client.post(
        "/api/v1/dispositivos",
        json={
            "codigo": "GLU-001",
            "nombre": "Glucómetro de prueba",
            "tipo": "GLUCEMIA",
        },
    )
    if disp_res.status_code == 201:
        dispositivo_id = disp_res.json()["id"]
    else:
        dispositivos = client.get("/api/v1/dispositivos").json()
        disp = next((d for d in dispositivos if d["codigo"] == "GLU-001"), dispositivos)
        dispositivo_id = disp["id"]

    return episodio_id, dispositivo_id


def test_guardar_resultado_glucemia_exitoso():
    episodio_id, dispositivo_id = obtener_o_crear_recursos_prueba()
    payload = {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo_id,
        "origen": "SENSOR",
        "data": {
            "valor": 110.5,
            "unidad": "mg/dL",
            "metodo": "FOTODIODO_NO_INVASIVO",
        },
    }
    response = client.post("/api/v1/glucemia/resultados", json=payload)
    assert response.status_code == 201
    res = response.json()
    assert res["modulo"] == "glucemia"
    assert res["data"]["valor"] == 110.5
    assert res["data"]["unidad"] == "mg/dL"


def test_guardar_resultado_valor_invalido():
    episodio_id, dispositivo_id = obtener_o_crear_recursos_prueba()
    payload = {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo_id,
        "origen": "SENSOR",
        "data": {
            "valor": "ciento diez",
            "unidad": "mg/dL",
            "metodo": "FOTODIODO_NO_INVASIVO",
        },
    }
    response = client.post("/api/v1/glucemia/resultados", json=payload)
    assert response.status_code == 422


def test_guardar_resultado_unidad_desconocida():
    episodio_id, dispositivo_id = obtener_o_crear_recursos_prueba()
    payload = {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo_id,
        "origen": "SENSOR",
        "data": {
            "valor": 110.5,
            "unidad": "PASCALES",
            "metodo": "FOTODIODO_NO_INVASIVO",
        },
    }
    response = client.post("/api/v1/glucemia/resultados", json=payload)
    assert response.status_code == 422


def test_guardar_resultado_episodio_inexistente():
    _, dispositivo_id = obtener_o_crear_recursos_prueba()
    payload = {
        "episodio_id": 999999,
        "dispositivo_id": dispositivo_id,
        "origen": "SENSOR",
        "data": {
            "valor": 100.0,
            "unidad": "mg/dL",
            "metodo": "FOTODIODO_NO_INVASIVO",
        },
    }
    response = client.post("/api/v1/glucemia/resultados", json=payload)
    assert response.status_code == 404