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

@pytest.fixture()
def episodio_valido(test_engine) -> EpisodioAtencion:
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="11111111",
            nombre="Paciente",
            apellido="Glucemia",
            fecha_nacimiento=date(1995, 5, 10),
            email="glucemia@example.test",
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)

        episodio = EpisodioAtencion(
            paciente_id=paciente.id,
            tipo_circuito="DEMOSTRACION_TECNICA",
        )
        session.add(episodio)
        session.commit()
        session.refresh(episodio)

        return episodio


@pytest.fixture()
def dispositivo_glucemia(test_engine) -> Dispositivo:
    with Session(test_engine) as session:
        dispositivo = Dispositivo(
            codigo="GLUCEMIA-TEST-001",
            nombre="Sensor de glucemia",
            tipo="GLUCEMIA",
        )
        session.add(dispositivo)
        session.commit()
        session.refresh(dispositivo)

        return dispositivo