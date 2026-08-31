from sqlmodel import Session, select

import app.core.database as database
from app.common.models import Dispositivo, EpisodioAtencion, Paciente, ResultadoModulo
from scripts import cargar_datos_demo


def test_cargador_de_datos_es_ejecutable_e_idempotente(
    test_engine, monkeypatch, capsys
):
    monkeypatch.setattr(database, "engine", test_engine)

    cargar_datos_demo.main()
    cargar_datos_demo.main()

    output = capsys.readouterr().out
    assert "Datos ficticios creados" in output
    assert "Datos ficticios ya existentes" in output

    with Session(test_engine) as session:
        assert len(session.exec(select(Paciente)).all()) == 1
        assert len(session.exec(select(EpisodioAtencion)).all()) == 1
        assert len(session.exec(select(Dispositivo)).all()) == 1
        assert len(session.exec(select(ResultadoModulo)).all()) == 1
