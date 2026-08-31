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