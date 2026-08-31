from sqlalchemy import inspect


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_swagger_openapi_incluye_las_rutas(client):
    docs_response = client.get("/docs")
    openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/demo-ambiente/resultados" in paths
    assert "/api/v1/demo-ambiente/resultados/{episodio_id}" in paths
    assert "/api/v1/demo-ambiente/simular" not in paths


def test_lifespan_crea_solamente_las_tablas_comunes(client, test_engine):
    tables = set(inspect(test_engine).get_table_names())

    assert tables == {
        "paciente",
        "episodio_atencion",
        "dispositivo",
        "resultado_modulo",
    }


def test_resultado_modulo_tiene_los_campos_del_contrato(client, test_engine):
    columns = inspect(test_engine).get_columns("resultado_modulo")
    column_names = {column["name"] for column in columns}

    assert column_names == {
        "id",
        "episodio_id",
        "dispositivo_id",
        "modulo",
        "data_json",
        "fecha_hora",
    }
