from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.common.models import EpisodioAtencion
from app.core.database import get_session
from app.models import Consentimiento
from .schemas import ConsentimientoCreate, ConsentimientoResponse

router = APIRouter(prefix="/api/v1/consentimientos", tags=["Consentimiento"])


@router.post("", response_model=ConsentimientoResponse, status_code=status.HTTP_201_CREATED)
def registrar_consentimiento(
    payload: ConsentimientoCreate, session: Session = Depends(get_session)
):
    """Registra la aceptación o rechazo del consentimiento para un episodio."""
    episodio = session.get(EpisodioAtencion, payload.episodio_id)
    if not episodio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El episodio de atención con ID {payload.episodio_id} no existe.",
        )

    statement = select(Consentimiento).where(Consentimiento.episodio_id == payload.episodio_id)
    consentimiento_existente = session.exec(statement).first()

    if consentimiento_existente:
        consentimiento_existente.version = payload.version
        consentimiento_existente.aceptado = payload.aceptado
        consentimiento_existente.observacion = payload.observacion
        consentimiento_existente.fecha_hora = datetime.now()

        session.add(consentimiento_existente)
        session.commit()
        session.refresh(consentimiento_existente)
        return consentimiento_existente

    nuevo_consentimiento = Consentimiento(
        episodio_id=payload.episodio_id,
        version=payload.version,
        aceptado=payload.aceptado,
        observacion=payload.observacion,
        fecha_hora=datetime.now(),
    )

    session.add(nuevo_consentimiento)
    session.commit()
    session.refresh(nuevo_consentimiento)

    return nuevo_consentimiento


@router.get("/{episodio_id}", response_model=ConsentimientoResponse)
def consultar_consentimiento(
    episodio_id: int, session: Session = Depends(get_session)
):
    """Consulta la decisión de consentimiento registrada para un episodio."""
    episodio = session.get(EpisodioAtencion, episodio_id)
    if not episodio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El episodio con ID {episodio_id} no existe.",
        )

    statement = select(Consentimiento).where(Consentimiento.episodio_id == episodio_id)
    consentimiento = session.exec(statement).first()

    if not consentimiento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha registrado consentimiento para el episodio {episodio_id}.",
        )

    return consentimiento