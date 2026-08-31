import json

from fastapi import HTTPException
from sqlmodel import Session, select

from app.common.models import (
    Dispositivo,
    EpisodioAtencion,
    ResultadoModulo,
)


def guardar_resultado(
    session: Session,
    episodio_id: int,
    dispositivo_id: int,
    modulo: str,
    data: dict,
) -> int:
    """Guarda los datos de cualquier módulo en la tabla común."""

    episodio = session.get(
        EpisodioAtencion,
        episodio_id,
    )

    if episodio is None:
        raise HTTPException(
            status_code=404,
            detail="El episodio no existe",
        )

    dispositivo = session.get(
        Dispositivo,
        dispositivo_id,
    )

    if dispositivo is None:
        raise HTTPException(
            status_code=404,
            detail="El dispositivo no existe",
        )

    resultado = ResultadoModulo(
        episodio_id=episodio_id,
        dispositivo_id=dispositivo_id,
        modulo=modulo,
        data_json=json.dumps(data),
    )

    session.add(resultado)
    session.commit()
    session.refresh(resultado)

    return resultado.id


def consultar_resultados(
    session: Session,
    episodio_id: int,
    modulo: str,
) -> list[dict]:
    """Obtiene los resultados de un módulo para un episodio."""

    episodio = session.get(
        EpisodioAtencion,
        episodio_id,
    )

    if episodio is None:
        raise HTTPException(
            status_code=404,
            detail="El episodio no existe",
        )

    consulta = select(ResultadoModulo).where(
        ResultadoModulo.episodio_id == episodio_id,
        ResultadoModulo.modulo == modulo,
    )

    resultados_guardados = session.exec(
        consulta
    ).all()

    resultados = []

    for resultado in resultados_guardados:
        resultados.append(
            {
                "id": resultado.id,
                "data": json.loads(
                    resultado.data_json
                ),
            }
        )

    return resultados


def consultar_todos_resultados(
    session: Session,
    modulo: str,
) -> list[dict]:
    """Obtiene todos los resultados de un módulo."""

    consulta = select(ResultadoModulo).where(
        ResultadoModulo.modulo == modulo
    )

    resultados_guardados = session.exec(
        consulta
    ).all()

    resultados = []

    for resultado in resultados_guardados:
        resultados.append(
            {
                "id": resultado.id,
                "episodio_id": resultado.episodio_id,
                "dispositivo_id": resultado.dispositivo_id,
                "data": json.loads(
                    resultado.data_json
                ),
                "fecha_hora": resultado.fecha_hora,
            }
        )

    return resultados