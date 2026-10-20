def test_inicio_carga_pantalla_y_script(client):
    pagina = client.get("/")

    assert pagina.status_code == 200
    assert "Prueba de Audiometría" in pagina.text
    assert "Comenzar" in pagina.text
    assert '<form id="form-inicio"' not in pagina.text
    assert "fecha_nacimiento" not in pagina.text
    assert "selector-episodio" not in pagina.text
    assert client.get("/static/js/inicio.js").status_code == 200


def test_comenzar_crea_episodio_nuevo_sin_reutilizar_los_anteriores(
    client, test_engine
):
    from app.common.models import EpisodioAtencion
    from sqlmodel import Session, select

    primero = client.post("/api/v1/episodios/audiometria")
    segundo = client.post("/api/v1/episodios/audiometria")

    assert primero.status_code == 201
    assert segundo.status_code == 201
    assert primero.json()["id"] != segundo.json()["id"]
    assert primero.json()["paciente_id"] == segundo.json()["paciente_id"]
    assert primero.json()["tipo_circuito"] == "DEMOSTRACION_OIDO"
    assert segundo.json()["tipo_circuito"] == "DEMOSTRACION_OIDO"
    assert primero.json()["estado"] == "INICIADO"
    assert segundo.json()["estado"] == "INICIADO"

    with Session(test_engine) as session:
        episodios = session.exec(
            select(EpisodioAtencion).where(
                EpisodioAtencion.tipo_circuito == "DEMOSTRACION_OIDO"
            )
        ).all()
        assert {episodio.id for episodio in episodios} == {
            primero.json()["id"],
            segundo.json()["id"],
        }
