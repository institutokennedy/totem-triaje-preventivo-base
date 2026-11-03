import json
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.database import get_session
from app.common.models import Dispositivo, EpisodioAtencion, Paciente, ResultadoModulo
from app.modules.unificacion.app.modules.contracts import (
    CONTRATOS_RESULTADOS,
    MODULOS_REQUERIDOS,
    RUTAS_CONSULTA_RESULTADOS,
    RUTAS_RESULTADOS,
    ResultadoBocaCreate,
    ResultadoECGCreate,
    ResultadoGlucemiaCreate,
    ResultadoOidoCreate,
    ResultadoSignosVitalesCreate,
    ResultadoVistaCreate,
)
from app.modules.informes.models import Informe  # noqa: F401  (registra la tabla)
from app.modules.informes.router import router as informes_router
from app.modules.unificacion.app.modules.router import router


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    app = FastAPI()
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).resolve().parents[5] / "app" / "static"),
        name="static",
    )
    app.include_router(router)
    app.include_router(informes_router)
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_e2e_informe_identifica_modulos(client: TestClient, session: Session):
    paciente = Paciente(
        dni="30123456",
        nombre="Juan",
        apellido="Pérez",
        fecha_nacimiento=date(2000, 1, 1),
    )
    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    episodio = EpisodioAtencion(
        paciente_id=paciente.id,
        tipo_circuito="PREVENTIVO",
        estado="EN_CURSO",
    )
    session.add(episodio)
    session.commit()
    session.refresh(episodio)
    episodio_id = episodio.id
    dispositivo = Dispositivo(
        codigo="UNIFICACION-TEST-001",
        nombre="Dispositivo de prueba",
        tipo="PRUEBA",
    )
    session.add(dispositivo)
    session.commit()
    session.refresh(dispositivo)

    for modulo, data in [
        ("signos_vitales", {"fc": 72, "spo2": 98}),
        ("ecg", {"ritmo": "sinusal"}),
        ("glucemia", {"valor_mg_dl": 95}),
    ]:
        session.add(
            ResultadoModulo(
                episodio_id=episodio_id,
                dispositivo_id=dispositivo.id,
                modulo=modulo,
                data_json=json.dumps(data),
            )
        )
    session.commit()

    traza = client.get(f"/api/v1/episodios/{episodio_id}/trazabilidad")
    assert traza.status_code == 200
    datos_traza = traza.json()
    assert datos_traza["modulos_completados"] == [
        "signos_vitales",
        "ecg",
        "glucemia",
    ]
    assert datos_traza["modulos_faltantes"] == ["boca", "vista", "oido"]
    assert datos_traza["circuito"] == "PREVENTIVO"
    assert datos_traza["detalles"][0]["data"] == {"fc": 72, "spo2": 98}

    resp = client.post(f"/api/v1/episodios/{episodio_id}/informes")
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 1
    assert body["episodio_id"] == episodio_id
    assert body["contenido"]["modulos_completados"] == [
        "Signos vitales",
        "ECG",
        "Glucemia",
    ]
    html = client.get(
        f"/api/v1/episodios/{episodio_id}/informes/{body['id']}/html"
    )
    assert html.status_code == 200
    assert "REPORTE PREVENTIVO DE TRIAJE" in html.text
    assert "Informe preventivo. No constituye un diagnóstico médico." in html.text

    rutas_informe = [
        ruta
        for ruta in client.app.routes
        if getattr(ruta, "path", None) == "/api/v1/episodios/{episodio_id}/informes"
    ]
    assert sorted(ruta.methods for ruta in rutas_informe) == [{"POST"}, {"GET"}]

    cierre = client.post(f"/api/v1/episodios/{episodio_id}/cerrar")
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "CERRADO"
    assert client.get(
        f"/api/v1/episodios/{episodio_id}/trazabilidad"
    ).json()["estado_episodio"] == "CERRADO"


def test_episodio_inexistente_404(client: TestClient):
    assert client.get("/api/v1/episodios/9999/trazabilidad").status_code == 404
    assert client.post("/api/v1/episodios/9999/informes").status_code == 404


def test_contratos_de_modulos_pendientes_conservan_identificadores_y_campos():
    rutas_esperadas = {
        "signos_vitales": "signos-vitales",
        "ecg": "ecg",
        "glucemia": "glucemia",
        "boca": "boca",
        "vista": "vista",
        "oido": "oido",
    }
    assert MODULOS_REQUERIDOS == tuple(rutas_esperadas)
    for modulo, slug in rutas_esperadas.items():
        ruta = f"/api/v1/{slug}/resultados"
        assert RUTAS_RESULTADOS[modulo] == ruta
        assert RUTAS_CONSULTA_RESULTADOS[modulo] == f"{ruta}/{{episodio_id}}"
        assert CONTRATOS_RESULTADOS[modulo]["post"] == ruta
        assert CONTRATOS_RESULTADOS[modulo]["get"] == f"{ruta}/{{episodio_id}}"
    assert CONTRATOS_RESULTADOS["signos_vitales"]["campos"] == (
        "presion_sistolica",
        "presion_diastolica",
        "frecuencia_cardiaca",
        "temperatura",
        "saturacion_oxigeno",
    )
    assert CONTRATOS_RESULTADOS["ecg"]["campos"] == (
        "frecuencia_muestreo_hz",
        "muestras",
        "unidad",
    )
    assert CONTRATOS_RESULTADOS["glucemia"]["campos"] == (
        "valor",
        "unidad",
        "metodo",
    )
    assert CONTRATOS_RESULTADOS["boca"]["campos"] == (
        "nombre_imagen",
        "observacion_tecnica",
    )
    assert CONTRATOS_RESULTADOS["vista"]["campos"] == (
        "prueba",
        "ojo_derecho",
        "ojo_izquierdo",
        "distancia_cm",
    )
    assert CONTRATOS_RESULTADOS["oido"]["campos"] == (
        "frecuencias_hz",
        "resultados_oido_derecho",
        "resultados_oido_izquierdo",
    )

    ejemplos = [
        (
            ResultadoSignosVitalesCreate,
            {
                "presion_sistolica": 118.0,
                "presion_diastolica": 76.0,
                "frecuencia_cardiaca": 74.0,
                "temperatura": 36.5,
                "saturacion_oxigeno": 98.0,
            },
        ),
        (
            ResultadoECGCreate,
            {
                "frecuencia_muestreo_hz": 250,
                "muestras": [0.02, 0.08, 0.31, 0.12, -0.04],
                "unidad": "mV",
            },
        ),
        (
            ResultadoGlucemiaCreate,
            {"valor": 123.4, "unidad": "mg/dL", "metodo": "SIMULADO"},
        ),
        (
            ResultadoBocaCreate,
            {
                "nombre_imagen": "boca_demo_01.jpg",
                "observacion_tecnica": "Imagen ficticia enfocada",
            },
        ),
        (
            ResultadoVistaCreate,
            {
                "prueba": "PRUEBA_DEMO",
                "ojo_derecho": "RESULTADO_DEMO_D",
                "ojo_izquierdo": "RESULTADO_DEMO_I",
                "distancia_cm": 300.0,
            },
        ),
        (
            ResultadoOidoCreate,
            {
                "frecuencias_hz": [500, 1000, 2000],
                "resultados_oido_derecho": [True, True, False],
                "resultados_oido_izquierdo": [True, False, False],
            },
        ),
    ]

    for schema, data in ejemplos:
        resultado = schema(
            episodio_id=15,
            dispositivo_id=4,
            origen="SIMULADOR",
            data=data,
        )
        assert resultado.data.model_dump(exclude_unset=True) == data


def test_pagina_resumen_del_modulo_unificado(client: TestClient):
    respuesta = client.get("/unificacion/episodios/1/resumen")

    assert respuesta.status_code == 200
    assert "Resumen de Atención" in respuesta.text

    script = client.get("/unificacion/resumen.js")
    assert script.status_code == 200
    assert "cargarTrazabilidad" in script.text
    assert "/api/v1/episodios/${episodioId}/cerrar" in script.text