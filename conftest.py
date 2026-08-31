from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.core.database as database
from app.common.models import Dispositivo, EpisodioAtencion, Paciente
from app.main import app


@pytest.fixture()
def test_engine(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = database.build_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(test_engine, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(database, "engine", test_engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def demo_references(test_engine, client) -> dict[str, int]:
    with Session(test_engine) as session:
        patient = Paciente(
            dni="00000000",
            nombre="Paciente",
            apellido="Ficticio",
            fecha_nacimiento=date(2000, 1, 1),
            email="paciente@example.test",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        episode = EpisodioAtencion(
            paciente_id=patient.id,
            tipo_circuito="DEMOSTRACION_TECNICA",
        )
        device = Dispositivo(
            codigo="DEMO-TEST-001",
            nombre="Dispositivo ficticio para pruebas",
            tipo="DEMOSTRACION_TECNICA",
        )
        session.add(episode)
        session.add(device)
        session.commit()
        session.refresh(episode)
        session.refresh(device)

        return {
            "paciente_id": patient.id,
            "episodio_id": episode.id,
            "dispositivo_id": device.id,
        }
