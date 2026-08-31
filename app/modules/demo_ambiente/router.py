from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.common.resultado_service import (
    consultar_resultados,
    consultar_todos_resultados,
    guardar_resultado,
)
from app.core.database import get_session
from app.modules.demo_ambiente.schemas import (
    EntradaAmbiente,
    RespuestaConsulta,
    RespuestaGuardado,
    ResultadoAmbienteCompleto,
)


MODULO = "demo_ambiente"


router = APIRouter(
    prefix="/api/v1/demo-ambiente",
    tags=["Demo ambiente"],
)


@router.post(
    "/resultados",
    response_model=RespuestaGuardado,
    status_code=201,
)
def recibir_resultado(
    entrada: EntradaAmbiente,
    session: Session = Depends(get_session),
) -> RespuestaGuardado:

    if entrada.origen not in [
        "SENSOR",
        "SIMULADOR",
    ]:
        raise HTTPException(
            status_code=422,
            detail="El origen debe ser SENSOR o SIMULADOR",
        )

    resultado_id = guardar_resultado(
        session=session,
        episodio_id=entrada.episodio_id,
        dispositivo_id=entrada.dispositivo_id,
        modulo=MODULO,
        data=entrada.data.model_dump(),
    )

    return {
        "mensaje": "Resultado guardado correctamente",
        "resultado_id": resultado_id,
    }


@router.get(
    "/resultados",
    response_model=list[ResultadoAmbienteCompleto],
)
def obtener_todos_resultados(
    session: Session = Depends(get_session),
):
    return consultar_todos_resultados(
        session=session,
        modulo=MODULO,
    )


@router.get(
    "/resultados/{episodio_id}",
    response_model=RespuestaConsulta,
)
def obtener_resultados(
    episodio_id: int,
    session: Session = Depends(get_session),
) -> RespuestaConsulta:

    resultados = consultar_resultados(
        session=session,
        episodio_id=episodio_id,
        modulo=MODULO,
    )

    return {
        "episodio_id": episodio_id,
        "modulo": MODULO,
        "resultados": resultados,
    }