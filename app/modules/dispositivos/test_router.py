RUTA = "/api/v1/dispositivos"


def test_crear_dispositivo(client):
    entrada = {
        "codigo": "ECG-001",
        "nombre": "Electrocardiógrafo ficticio",
        "tipo": "ECG",
    }

    response = client.post(
        RUTA,
        json=entrada,
    )

    assert response.status_code == 201

    datos = response.json()

    assert datos["codigo"] == "ECG-001"
    assert datos["nombre"] == "Electrocardiógrafo ficticio"
    assert datos["tipo"] == "ECG"
    assert datos["estado"] == "DISPONIBLE"
    assert datos["activo"] is True
    assert "id" in datos


def test_no_permitir_codigo_duplicado(client):
    entrada = {
        "codigo": "ECG-001",
        "nombre": "Electrocardiógrafo ficticio",
        "tipo": "ECG",
    }

    client.post(
        RUTA,
        json=entrada,
    )

    response = client.post(
        RUTA,
        json=entrada,
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Ya existe un dispositivo con ese código"
    }


def test_listar_dispositivos(client):
    entrada = {
        "codigo": "SV-001",
        "nombre": "Equipo de signos vitales",
        "tipo": "SIGNOS_VITALES",
    }

    client.post(
        RUTA,
        json=entrada,
    )

    response = client.get(RUTA)

    assert response.status_code == 200

    dispositivos = response.json()

    assert len(dispositivos) == 1
    assert dispositivos[0]["codigo"] == "SV-001"


def test_obtener_dispositivo(client):
    entrada = {
        "codigo": "VISTA-001",
        "nombre": "Equipo de evaluación visual",
        "tipo": "VISTA",
    }

    creado = client.post(
        RUTA,
        json=entrada,
    ).json()

    dispositivo_id = creado["id"]

    response = client.get(
        f"{RUTA}/{dispositivo_id}"
    )

    assert response.status_code == 200
    assert response.json()["codigo"] == "VISTA-001"


def test_dispositivo_inexistente(client):
    response = client.get(
        f"{RUTA}/999"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "El dispositivo no existe"
    }