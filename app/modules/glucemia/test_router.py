from datetime import date
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.common.models import Dispositivo, EpisodioAtencion, Paciente
from app.main import app

client = TestClient(app)


def test_glucemia_flujo_completo_y_validaciones(session: Session):
    """
    Pruebas mínimas del Módulo de Glucemia (Grupo 3):
    1. Registro de paciente, episodio y dispositivo (GLU-001).
    2. Envío de resultado válido (HTTP 201).
    3. Errores de validación técnica (HTTP 422).
    4. Errores de recursos no encontrados (HTTP 404).
    5. Consulta de resultados guardados (HTTP 200).
    """
    # 1. Crear Paciente con objeto de tipo date (resuelve el error de tipo de fecha)
    paciente = Paciente(
        dni="12345678",
        nombre="Juan",
        apellido="Pérez",
        fecha_nacimiento=date.fromisoformat("1990-01-01"),
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    # Afirmar que el id fue asignado por la BD (resuelve el error int | None de Pylance)
    assert paciente.id is not None

    # 2. Crear Episodio de Atención asociado
    episodio = EpisodioAtencion(paciente_id=paciente.id, tipo_circuito="GUARDIA")
    session.add(episodio)
    session.commit()
    session.refresh(episodio)

    assert episodio.id is not None

    # 3. Crear Dispositivo de prueba
    dispositivo = Dispositivo(
        codigo="GLU-001", nombre="Glucómetro Prueba", tipo="GLUCEMIA"
    )
    session.add(dispositivo)
    session.commit()
    session.refresh(dispositivo)

    assert dispositivo.id is not None

    # 4. Caso válido (HTTP 201 Created)
    payload_valido = {
        "episodio_id": episodio.id,
        "dispositivo_id": dispositivo.id,
        "origen": "SIMULADOR",
        "data": {"valor": 110.5, "unidad": "mg/dL", "metodo": "SIMULADO"},
    }
    response = client.post("/api/v1/glucemia/resultados", json=payload_valido)
    assert response.status_code == 201
    res_json = response.json()
    assert res_json["data"]["valor"] == 110.5
    assert res_json["modulo"] == "glucemia"

    # 5. Caso error: valor enviado como texto o inválido (HTTP 422)
    payload_texto = {
        "episodio_id": episodio.id,
        "dispositivo_id": dispositivo.id,
        "origen": "SIMULADOR",
        "data": {"valor": "ciento diez", "unidad": "mg/dL", "metodo": "SIMULADO"},
    }
    response_texto = client.post("/api/v1/glucemia/resultados", json=payload_texto)
    assert response_texto.status_code == 422

    # 6. Caso error: unidad no permitida (HTTP 422)
    payload_unidad = {
        "episodio_id": episodio.id,
        "dispositivo_id": dispositivo.id,
        "origen": "SIMULADOR",
        "data": {"valor": 100.0, "unidad": "g/L", "metodo": "SIMULADO"},
    }
    response_unidad = client.post("/api/v1/glucemia/resultados", json=payload_unidad)
    assert response_unidad.status_code == 422

    # 7. Caso error: falta método (HTTP 422)
    payload_sin_metodo = {
        "episodio_id": episodio.id,
        "dispositivo_id": dispositivo.id,
        "origen": "SIMULADOR",
        "data": {"valor": 100.0, "unidad": "mg/dL", "metodo": ""},
    }
    response_metodo = client.post(
        "/api/v1/glucemia/resultados", json=payload_sin_metodo
    )
    assert response_metodo.status_code == 422

    # 8. Caso error: episodio inexistente (HTTP 404)
    payload_ep_404 = {
        "episodio_id": 99999,
        "dispositivo_id": dispositivo.id,
        "origen": "SIMULADOR",
        "data": {"valor": 100.0, "unidad": "mg/dL", "metodo": "SIMULADO"},
    }
    response_ep = client.post("/api/v1/glucemia/resultados", json=payload_ep_404)
    assert response_ep.status_code == 404

    # 9. Caso error: dispositivo inexistente (HTTP 404)
    payload_disp_404 = {
        "episodio_id": episodio.id,
        "dispositivo_id": 99999,
        "origen": "SIMULADOR",
        "data": {"valor": 100.0, "unidad": "mg/dL", "metodo": "SIMULADO"},
    }
    response_disp = client.post("/api/v1/glucemia/resultados", json=payload_disp_404)
    assert response_disp.status_code == 404

    # 10. Consulta de resultados persistidos (HTTP 200)
    get_response = client.get(f"/api/v1/glucemia/resultados/{episodio.id}")
    assert get_response.status_code == 200
    resultados = get_response.json()
    assert len(resultados) == 1
    assert resultados["data"]["valor"] == 110.5