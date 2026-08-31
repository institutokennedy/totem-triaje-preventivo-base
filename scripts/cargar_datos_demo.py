from datetime import date

from sqlmodel import Session, select

import app.core.database as database
from app.common.models import Dispositivo, EpisodioAtencion, Paciente, ResultadoModulo
from app.common.resultado_service import guardar_resultado
from app.modules.demo_ambiente.router import MODULO
from app.modules.demo_ambiente.simulator import generar_entrada_ficticia


def get_or_create_patient(session: Session) -> Paciente:
    patient = session.exec(select(Paciente).where(Paciente.dni == "00000000")).first()
    if patient is None:
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
    return patient


def get_or_create_device(session: Session) -> Dispositivo:
    device = session.exec(
        select(Dispositivo).where(Dispositivo.codigo == "DEMO-AMBIENTE-001")
    ).first()
    if device is None:
        device = Dispositivo(
            codigo="DEMO-AMBIENTE-001",
            nombre="Sensor ambiental simulado",
            tipo="DEMOSTRACION_TECNICA",
        )
        session.add(device)
        session.commit()
        session.refresh(device)
    return device


def get_or_create_episode(session: Session, patient: Paciente) -> EpisodioAtencion:
    episode = session.exec(
        select(EpisodioAtencion).where(
            EpisodioAtencion.paciente_id == patient.id,
            EpisodioAtencion.tipo_circuito == "DEMOSTRACION_TECNICA",
        )
    ).first()
    if episode is None:
        episode = EpisodioAtencion(
            paciente_id=patient.id,
            tipo_circuito="DEMOSTRACION_TECNICA",
        )
        session.add(episode)
        session.commit()
        session.refresh(episode)
    return episode


def main() -> None:
    database.create_db_and_tables()
    with Session(database.engine) as session:
        patient = get_or_create_patient(session)
        device = get_or_create_device(session)
        episode = get_or_create_episode(session, patient)

        existing_result = session.exec(
            select(ResultadoModulo).where(
                ResultadoModulo.episodio_id == episode.id,
                ResultadoModulo.modulo == MODULO,
            )
        ).first()
        if existing_result is None:
            entrada = generar_entrada_ficticia(
                episodio_id=episode.id,
                dispositivo_id=device.id,
            )
            result_id = guardar_resultado(
                session=session,
                episodio_id=entrada["episodio_id"],
                dispositivo_id=entrada["dispositivo_id"],
                modulo=MODULO,
                data=entrada["data"],
            )
            action = "creados"
        else:
            result_id = existing_result.id
            action = "ya existentes"

        # SQLAlchemy expira objetos después de cada commit. Se copian los IDs
        # mientras la sesión sigue abierta para poder mostrarlos al finalizar.
        patient_id = patient.id
        episode_id = episode.id
        device_id = device.id

    print("Datos ficticios", action)
    print(f"Paciente ID: {patient_id}")
    print(f"Episodio ID: {episode_id}")
    print(f"Dispositivo ID: {device_id}")
    print(f"Resultado de demostración ID: {result_id}")


if __name__ == "__main__":
    main()
