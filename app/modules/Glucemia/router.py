import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

# Importaciones ajustadas a la estructura de tu repositorio
from app.common.models import Dispositivo, EpisodioAtencion, ResultadoModulo
from app.core.database import get_session
from .schemas import ResultadoGlucemiaCreate

router = APIRouter(prefix="/api/v1/glucemia", tags=["Glucemia"])


@router.post("/resultados", status_code=status.HTTP_201_CREATED)
def guardar_resultado_glucemia(
    payload: ResultadoGlucemiaCreate, session: Session = Depends(get_session)
):
    """Guarda una medición validada de glucemia en un episodio."""
    # 1. Verificar que el episodio de atención exista en SQLite
    episodio = session.get(EpisodioAtencion, payload.episodio_id)
    if not episodio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El episodio de atención con ID {payload.episodio_id} no existe.",
        )

    # 2. Verificar que el dispositivo exista en SQLite
    dispositivo = session.get(Dispositivo, payload.dispositivo_id)
    if not dispositivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El dispositivo con ID {payload.dispositivo_id} no existe.",
        )

    # 3. Convertir data a diccionario (compatible con Pydantic v1 y v2)
    if hasattr(payload.data, "model_dump"):
        data_dict = payload.data.model_dump()
    else:
        data_dict = payload.data.dict()

    data_json_str = json.dumps(data_dict)

    # 4. Guardar en la tabla común ResultadoModulo con modulo = "glucemia"
    nuevo_resultado = ResultadoModulo(
        episodio_id=payload.episodio_id,
        dispositivo_id=payload.dispositivo_id,
        modulo="glucemia",
        data_json=data_json_str,
    )

    session.add(nuevo_resultado)
    session.commit()
    session.refresh(nuevo_resultado)

    return {
        "id": nuevo_resultado.id,
        "episodio_id": nuevo_resultado.episodio_id,
        "dispositivo_id": nuevo_resultado.dispositivo_id,
        "modulo": nuevo_resultado.modulo,
        "data": data_dict,
        "fecha_hora": nuevo_resultado.fecha_hora,
    }


@router.get("/resultados/{episodio_id}")
def consultar_resultados_glucemia(
    episodio_id: int, session: Session = Depends(get_session)
):
    """Recupera los resultados de glucemia registrados para un episodio."""
    episodio = session.get(EpisodioAtencion, episodio_id)
    if not episodio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El episodio con ID {episodio_id} no existe.",
        )

    statement = select(ResultadoModulo).where(
        ResultadoModulo.episodio_id == episodio_id,
        ResultadoModulo.modulo == "glucemia",
    )
    resultados = session.exec(statement).all()

    respuesta = []
    for r in resultados:
        data_dict = json.loads(r.data_json) if r.data_json else {}
        respuesta.append(
            {
                "id": r.id,
                "episodio_id": r.episodio_id,
                "dispositivo_id": r.dispositivo_id,
                "modulo": r.modulo,
                "data": data_dict,
                "fecha_hora": r.fecha_hora,
            }
        )

    return respuesta