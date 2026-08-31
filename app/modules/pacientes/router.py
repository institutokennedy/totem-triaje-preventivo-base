from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.common.models import Paciente
from app.core.database import get_session
from app.modules.pacientes.schemas import (
    PacienteCrear,
    PacienteRespuesta,
)


router = APIRouter(
    prefix="/api/v1/pacientes",
    tags=["Pacientes"],
)


@router.post(
    "",
    response_model=PacienteRespuesta,
    status_code=201,
)
def crear_paciente(
    entrada: PacienteCrear,
    session: Session = Depends(get_session),
):
    consulta = select(Paciente).where(
        Paciente.dni == entrada.dni
    )

    paciente_existente = session.exec(consulta).first()

    if paciente_existente is not None:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un paciente con ese DNI",
        )

    paciente = Paciente(
        dni=entrada.dni,
        nombre=entrada.nombre,
        apellido=entrada.apellido,
        fecha_nacimiento=entrada.fecha_nacimiento,
        email=entrada.email,
        telefono=entrada.telefono,
    )

    session.add(paciente)
    session.commit()
    session.refresh(paciente)

    return paciente


@router.get(
    "",
    response_model=list[PacienteRespuesta],
)
def listar_pacientes(
    session: Session = Depends(get_session),
):
    consulta = select(Paciente)

    pacientes = session.exec(consulta).all()

    return pacientes


@router.get(
    "/{paciente_id}",
    response_model=PacienteRespuesta,
)
def obtener_paciente(
    paciente_id: int,
    session: Session = Depends(get_session),
):
    paciente = session.get(Paciente, paciente_id)

    if paciente is None:
        raise HTTPException(
            status_code=404,
            detail="El paciente no existe",
        )

    return paciente