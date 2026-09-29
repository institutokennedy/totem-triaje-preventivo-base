from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_session
from app.models import Dispositivo, EpisodioAtencion, Paciente
from app.modules.oido.router import router


def _crear_datos_base(session: Session):
    paciente = Paciente(
        dni="12345678",
        nombre="Test",
        apellido="Paciente",
        fecha_nacimiento=date(1990, 1, 1),
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    episodio = EpisodioAtencion(paciente_id=paciente.id, tipo_circuito="CONSULTA")
    session.add(episodio)
    dispositivo = Dispositivo(codigo="OIDO-001", nombre="Audiometría", tipo="OIDO")
    session.add(dispositivo)
    session.commit()
    session.refresh(episodio)
    session.refresh(dispositivo)
    return episodio.id, dispositivo.id


@pytest.fixture
def entorno():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    app = FastAPI()
    app.include_router(router)

    def _get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _get_session

    with Session(engine) as s:
        episodio_id, dispositivo_id = _crear_datos_base(s)

    return TestClient(app), episodio_id, dispositivo_id


def _payload(episodio_id, dispositivo_id, **data_overrides):
    data = {
        "frecuencias_hz": [500, 1000, 2000],
        "resultados_oido_derecho": [True, True, False],
        "resultados_oido_izquierdo": [True, False, False],
    }
    data.update(data_overrides)
    return {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo_id,
        "origen": "SIMULADOR",
        "data": data,
    }


def test_crear_resultado_exitoso(entorno):
    client, ep, disp = entorno
    r = client.post("/api/v1/oido/resultados", json=_payload(ep, disp))
    assert r.status_code == 201
    assert r.json()["modulo"] == "oido"

    r = client.get(f"/api/v1/oido/resultados/{ep}")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["data_json"]["frecuencias_hz"] == [500, 1000, 2000]


def test_listas_vacias(entorno):
    client, ep, disp = entorno
    p = _payload(
        ep, disp,
        frecuencias_hz=[], resultados_oido_derecho=[], resultados_oido_izquierdo=[],
    )
    assert client.post("/api/v1/oido/resultados", json=p).status_code == 422


def test_longitudes_desiguales(entorno):
    client, ep, disp = entorno
    p = _payload(ep, disp, resultados_oido_derecho=[True, False])
    assert client.post("/api/v1/oido/resultados", json=p).status_code == 422


@pytest.mark.parametrize("frecuencias", [[500, 0, 2000], [500, -1000, 2000], [500, "abc", 2000]])
def test_frecuencia_invalida_o_no_numerica(entorno, frecuencias):
    client, ep, disp = entorno
    p = _payload(ep, disp, frecuencias_hz=frecuencias)
    assert client.post("/api/v1/oido/resultados", json=p).status_code == 422


def test_episodio_inexistente(entorno):
    client, ep, disp = entorno
    r = client.post("/api/v1/oido/resultados", json=_payload(99999, disp))
    assert r.status_code == 404


def test_dispositivo_inexistente(entorno):
    client, ep, disp = entorno
    r = client.post("/api/v1/oido/resultados", json=_payload(ep, 99999))
    assert r.status_code == 404