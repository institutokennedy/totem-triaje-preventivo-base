from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.common.models import EpisodioAtencion, Paciente
from app.core.database import get_session
from app.modules.episodios.schemas import (
    EpisodioCrear,
    EpisodioRespuesta,
)


router = APIRouter(
    prefix="/api/v1/episodios",
    tags=["Episodios"],
)

AUDIO_DEMO_EMAIL = "audiometria-demo@invalid.local"
AUDIO_DEMO_DNI_RANGE = range(99999999, 99989999, -1)


@router.post(
    "/audiometria",
    response_model=EpisodioRespuesta,
    status_code=201,
    summary="Iniciar una nueva prueba de audiometría",
)
def crear_episodio_audiometria(
    session: Session = Depends(get_session),
):
    paciente = session.exec(
        select(Paciente).where(Paciente.email == AUDIO_DEMO_EMAIL)
    ).first()

    if paciente is None:
        dnis_existentes = set(session.exec(select(Paciente.dni)).all())
        dni_disponible = next(
            (
                str(dni)
                for dni in AUDIO_DEMO_DNI_RANGE
                if str(dni) not in dnis_existentes
            ),
            None,
        )
        if dni_disponible is None:
            raise HTTPException(
                status_code=503,
                detail="No se pudo preparar el paciente ficticio de audiometría",
            )
        paciente = Paciente(
            dni=dni_disponible,
            nombre="Paciente",
            apellido="De prueba",
            fecha_nacimiento=date(2000, 1, 1),
            email=AUDIO_DEMO_EMAIL,
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)

    episodio = EpisodioAtencion(
        paciente_id=paciente.id,
        tipo_circuito="DEMOSTRACION_OIDO",
    )
    session.add(episodio)
    session.commit()
    session.refresh(episodio)
    return episodio


@router.post(
    "",
    response_model=EpisodioRespuesta,
    status_code=201,
)
def crear_episodio(
    entrada: EpisodioCrear,
    session: Session = Depends(get_session),
):
    paciente = session.get(
        Paciente,
        entrada.paciente_id,
    )

    if paciente is None:
        raise HTTPException(
            status_code=404,
            detail="El paciente no existe",
        )

    episodio = EpisodioAtencion(
        paciente_id=entrada.paciente_id,
        tipo_circuito=entrada.tipo_circuito,
    )

    session.add(episodio)
    session.commit()
    session.refresh(episodio)

    return episodio


@router.get(
    "",
    response_model=list[EpisodioRespuesta],
)
def listar_episodios(
    session: Session = Depends(get_session),
):
    consulta = select(EpisodioAtencion)

    episodios = session.exec(consulta).all()

    return episodios


@router.get(
    "/{episodio_id}",
    response_model=EpisodioRespuesta,
)
def obtener_episodio(
    episodio_id: int,
    session: Session = Depends(get_session),
):
    episodio = session.get(
        EpisodioAtencion,
        episodio_id,
    )

    if episodio is None:
        raise HTTPException(
            status_code=404,
            detail="El episodio no existe",
        )

    return episodio