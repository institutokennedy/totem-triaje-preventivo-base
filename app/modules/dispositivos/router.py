from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.common.models import Dispositivo
from app.core.database import get_session
from app.modules.dispositivos.schemas import DispositivoRespuesta


router = APIRouter(
    prefix="/api/v1/dispositivos",
    tags=["Dispositivos"],
)


@router.get(
    "",
    response_model=list[DispositivoRespuesta],
)
def listar_dispositivos(
    session: Session = Depends(get_session),
):
    consulta = select(Dispositivo)

    dispositivos = session.exec(consulta).all()

    return dispositivos


@router.get(
    "/{dispositivo_id}",
    response_model=DispositivoRespuesta,
)
def obtener_dispositivo(
    dispositivo_id: int,
    session: Session = Depends(get_session),
):
    dispositivo = session.get(
        Dispositivo,
        dispositivo_id,
    )

    if dispositivo is None:
        raise HTTPException(
            status_code=404,
            detail="El dispositivo no existe",
        )

    return dispositivo