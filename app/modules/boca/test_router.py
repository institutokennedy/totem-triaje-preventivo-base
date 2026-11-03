import pytest
from fastapi.testclient import TestClient

def test_guardar_resultado_boca_valido(client: TestClient, episodio_fixture, dispositivo_boca_fixture):
    payload = {
        "episodio_id": episodio_fixture.id,
        "dispositivo_id": dispositivo_boca_fixture.id,
        "origen": "SIMULADOR",
        "data": {
            "nombre_imagen": "boca_captura_01.jpg",
            "observacion_tecnica": "Imagen ficticia correcta"
        }
    }
    response = client.post("/api/v1/boca/resultados", json=payload)
    assert response.status_code == 201
    assert response.json()["mensaje"] == "Resultado guardado correctamente"
    assert "resultado_id" in response.json()

def test_guardar_resultado_boca_extension_invalida(client: TestClient, episodio_fixture, dispositivo_boca_fixture):
    payload = {
        "episodio_id": episodio_fixture.id,
        "dispositivo_id": dispositivo_boca_fixture.id,
        "origen": "SIMULADOR",
        "data": {
            "nombre_imagen": "archivo_incorrecto.pdf"
        }
    }
    response = client.post("/api/v1/boca/resultados", json=payload)
    assert response.status_code == 422

def test_guardar_resultado_boca_episodio_inexistente(client: TestClient, dispositivo_boca_fixture):
    payload = {
        "episodio_id": 99999,
        "dispositivo_id": dispositivo_boca_fixture.id,
        "origen": "SIMULADOR",
        "data": {
            "nombre_imagen": "boca_captura_02.png"
        }
    }
    response = client.post("/api/v1/boca/resultados", json=payload)
    assert response.status_code == 404

def test_consultar_resultados_boca(client: TestClient, episodio_fixture):
    response = client.get(f"/api/v1/boca/resultados/{episodio_fixture.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["episodio_id"] == episodio_fixture.id
    assert data["modulo"] == "boca"
    assert isinstance(data["resultados"], list)