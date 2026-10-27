from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_session
from app.models import Dispositivo, EpisodioAtencion, Paciente
from app.modules.oido.router import limpiar_respuestas, router


@pytest.fixture(autouse=True)
def _buffer_limpio():
    limpiar_respuestas()
    yield
    limpiar_respuestas()


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
    assert r.json()["origen"] == "SIMULADOR"

    r = client.get(f"/api/v1/oido/resultados/{ep}")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["data_json"]["frecuencias_hz"] == [500, 1000, 2000]
    assert r.json()[0]["data_json"]["nivel_senal"] == "NORMAL"


def test_crear_resultado_con_lados_aleatorios(entorno):
    client, ep, disp = entorno
    r = client.post(
        "/api/v1/oido/resultados",
        json={
            "episodio_id": ep,
            "dispositivo_id": disp,
            "origen": "ESP32",
            "data": {
                "ensayos": [
                    {
                        "frecuencia_hz": 500,
                        "lado_estimulo": "IZQUIERDO",
                        "respuesta": "DERECHO",
                    },
                    {
                        "frecuencia_hz": 500,
                        "lado_estimulo": "DERECHO",
                        "respuesta": "NO_ESCUCHE",
                    },
                ]
            },
        },
    )

    assert r.status_code == 201
    ensayos = r.json()["data_json"]["ensayos"]
    assert ensayos[0]["lado_estimulo"] == "IZQUIERDO"
    assert ensayos[0]["respuesta"] == "DERECHO"
    assert ensayos[1]["respuesta"] == "NO_ESCUCHE"


def test_resultado_con_ensayo_invalido_o_formatos_mezclados(entorno):
    client, ep, disp = entorno
    base = {
        "episodio_id": ep,
        "dispositivo_id": disp,
        "origen": "ESP32",
        "data": {
            "ensayos": [
                {
                    "frecuencia_hz": 500,
                    "lado_estimulo": "CENTRO",
                    "respuesta": "DERECHO",
                }
            ]
        },
    }

    assert client.post("/api/v1/oido/resultados", json=base).status_code == 422

    base["data"] = {
        "ensayos": [
            {
                "frecuencia_hz": 500,
                "lado_estimulo": "IZQUIERDO",
                "respuesta": "DERECHO",
            }
        ],
        "frecuencias_hz": [500],
        "resultados_oido_derecho": [True],
        "resultados_oido_izquierdo": [False],
    }
    assert client.post("/api/v1/oido/resultados", json=base).status_code == 422


def test_resultado_guarda_nivel_de_senal_reducido(entorno):
    client, ep, disp = entorno
    r = client.post(
        "/api/v1/oido/resultados",
        json=_payload(
            ep,
            disp,
            nivel_senal="REDUCIDO_POR_AUTOINFORME",
        ),
    )

    assert r.status_code == 201
    assert r.json()["data_json"]["nivel_senal"] == "REDUCIDO_POR_AUTOINFORME"


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


# ----------------------------------------------------- respuestas del joystick
def test_respuesta_joystick_publicar_y_consultar(entorno):
    client, _, disp = entorno

    r = client.post("/api/v1/oido/respuestas", json={"dispositivo_id": disp, "respuesta": True})
    assert r.status_code == 201
    seq = r.json()["seq"]

    r = client.get(f"/api/v1/oido/respuestas/{disp}", params={"despues_de": 0})
    assert r.status_code == 200
    assert [x["respuesta"] for x in r.json()["respuestas"]] == [True]
    assert r.json()["ultimo"] == seq

    # con el cursor al día no hay respuestas nuevas
    r = client.get(f"/api/v1/oido/respuestas/{disp}", params={"despues_de": seq})
    assert r.json()["respuestas"] == []

    client.post("/api/v1/oido/respuestas", json={"dispositivo_id": disp, "respuesta": False})
    r = client.get(f"/api/v1/oido/respuestas/{disp}", params={"despues_de": seq})
    assert [x["respuesta"] for x in r.json()["respuestas"]] == [False]


@pytest.mark.parametrize("lado", ["IZQUIERDO", "DERECHO"])
def test_respuesta_joystick_acepta_lado(lado, entorno):
    client, _, disp = entorno
    r = client.post(
        "/api/v1/oido/respuestas",
        json={"dispositivo_id": disp, "respuesta": lado},
    )

    assert r.status_code == 201
    assert r.json()["respuesta"] == lado


def test_respuesta_joystick_acepta_pulsacion_no_escuche(entorno):
    client, _, disp = entorno
    r = client.post(
        "/api/v1/oido/respuestas",
        json={"dispositivo_id": disp, "respuesta": "NO_ESCUCHE"},
    )

    assert r.status_code == 201
    assert r.json()["respuesta"] == "NO_ESCUCHE"


def test_respuesta_joystick_dispositivo_inexistente(entorno):
    client, _, _ = entorno
    r = client.post("/api/v1/oido/respuestas", json={"dispositivo_id": 99999, "respuesta": True})
    assert r.status_code == 404


@pytest.mark.parametrize("valor", ["si", 1, None])
def test_respuesta_joystick_no_booleana(entorno, valor):
    client, _, disp = entorno
    r = client.post("/api/v1/oido/respuestas", json={"dispositivo_id": disp, "respuesta": valor})
    assert r.status_code == 422