import json

from sqlmodel import Session, select

from app.common.models import ResultadoModulo
from app.modules.demo_ambiente.simulator import generar_entrada_ficticia


RUTA = "/api/v1/demo-ambiente/resultados"


def test_guardar_resultado(client, test_engine, demo_references):
    entrada = generar_entrada_ficticia(
        episodio_id=demo_references["episodio_id"],
        dispositivo_id=demo_references["dispositivo_id"],
    )

    response = client.post(RUTA, json=entrada)

    assert response.status_code == 201
    assert response.json() == {
        "mensaje": "Resultado guardado correctamente",
        "resultado_id": 1,
    }

    with Session(test_engine) as session:
        resultado = session.exec(select(ResultadoModulo)).one()

    assert json.loads(resultado.data_json) == entrada["data"]


def test_consultar_resultados(client, demo_references):
    entrada = generar_entrada_ficticia(
        episodio_id=demo_references["episodio_id"],
        dispositivo_id=demo_references["dispositivo_id"],
    )
    client.post(RUTA, json=entrada)

    response = client.get(f"{RUTA}/{demo_references['episodio_id']}")

    assert response.status_code == 200
    assert response.json() == {
        "episodio_id": demo_references["episodio_id"],
        "modulo": "demo_ambiente",
        "resultados": [
            {
                "id": 1,
                "data": entrada["data"],
            }
        ],
    }


def test_episodio_inexistente(client, demo_references):
    entrada = generar_entrada_ficticia(
        episodio_id=999,
        dispositivo_id=demo_references["dispositivo_id"],
    )

    response = client.post(RUTA, json=entrada)

    assert response.status_code == 404
    assert response.json() == {"detail": "El episodio no existe"}


def test_falta_un_campo_obligatorio(client, demo_references):
    entrada = {
        "episodio_id": demo_references["episodio_id"],
        "dispositivo_id": demo_references["dispositivo_id"],
        "origen": "SIMULADOR",
    }

    response = client.post(RUTA, json=entrada)

    assert response.status_code == 422


def test_origen_incorrecto(client, demo_references):
    entrada = generar_entrada_ficticia(
        episodio_id=demo_references["episodio_id"],
        dispositivo_id=demo_references["dispositivo_id"],
    )
    entrada["origen"] = "MANUAL"

    response = client.post(RUTA, json=entrada)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "El origen debe ser SENSOR o SIMULADOR"
    }
