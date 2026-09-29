import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

# Contrato del repo base: get_session y los modelos comunes se consumen sin modificarse.
from app.database import get_session
from app.models import EpisodioAtencion, Paciente, ResultadoModulo
from app.modules.informes.models import Informe

router = APIRouter(prefix="/api/v1/episodios", tags=["informes"])

LEYENDA_LEGAL = "Informe preventivo. No constituye un diagnóstico médico."

# Valor de ResultadoModulo.modulo -> nombre visible
MODULOS = {
    "signos_vitales": "Signos Vitales",
    "ecg": "ECG",
    "glucemia": "Glucemia",
    "boca": "Boca",
    "vista": "Vista",
    "oido": "Oído",
}


class InformeCreate(BaseModel):
    tipo_informe: str = "COMPLETO"


def _serializar(informe: Informe) -> dict:
    salida = informe.model_dump(mode="json")
    try:
        salida["contenido_json"] = json.loads(informe.contenido_json)
    except (TypeError, ValueError):
        pass
    return salida


def _obtener_episodio_y_paciente(session: Session, episodio_id: int):
    episodio = session.get(EpisodioAtencion, episodio_id)
    if episodio is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    paciente = session.get(Paciente, episodio.paciente_id)
    if paciente is None:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return episodio, paciente


def _resultados_por_modulo(session: Session, episodio_id: int) -> dict:
    registros = session.exec(
        select(ResultadoModulo).where(ResultadoModulo.episodio_id == episodio_id)
    ).all()
    agrupados: dict = {}
    for r in registros:
        try:
            data = json.loads(r.data_json)
        except (TypeError, ValueError):
            data = r.data_json
        agrupados.setdefault(r.modulo, []).append(
            {
                "origen": getattr(r, "origen", None),
                "dispositivo_id": getattr(r, "dispositivo_id", None),
                "data": data,
            }
        )
    return agrupados


def _estado_modulos(agrupados: dict):
    completados = [nombre for clave, nombre in MODULOS.items() if clave in agrupados]
    pendientes = [nombre for clave, nombre in MODULOS.items() if clave not in agrupados]
    return completados, pendientes


@router.get("/{episodio_id}/resumen")
def resumen_episodio(episodio_id: int, session: Session = Depends(get_session)):
    episodio, paciente = _obtener_episodio_y_paciente(session, episodio_id)
    completados, pendientes = _estado_modulos(_resultados_por_modulo(session, episodio_id))
    return {
        "paciente": paciente.model_dump(mode="json"),
        "episodio": episodio.model_dump(mode="json"),
        "modulos_completados": completados,
        "modulos_pendientes": pendientes,
    }


@router.post("/{episodio_id}/informes", status_code=status.HTTP_201_CREATED)
def generar_informe(
    episodio_id: int,
    payload: Optional[InformeCreate] = None,
    session: Session = Depends(get_session),
):
    payload = payload or InformeCreate()
    episodio, paciente = _obtener_episodio_y_paciente(session, episodio_id)
    agrupados = _resultados_por_modulo(session, episodio_id)
    completados, pendientes = _estado_modulos(agrupados)

    contenido = {
        "leyenda": LEYENDA_LEGAL,
        "paciente": paciente.model_dump(mode="json"),
        "episodio": episodio.model_dump(mode="json"),
        "modulos_completados": completados,
        "modulos_pendientes": pendientes,
        "resultados": agrupados,
    }

    previos = session.exec(select(Informe).where(Informe.episodio_id == episodio_id)).all()
    version = max((i.version for i in previos), default=0) + 1

    informe = Informe(
        episodio_id=episodio_id,
        tipo_informe=payload.tipo_informe,
        contenido_json=json.dumps(contenido, ensure_ascii=False),
        estado="GENERADO",
        version=version,
    )
    session.add(informe)
    session.commit()
    session.refresh(informe)
    return _serializar(informe)


@router.get("/{episodio_id}/informes", response_model=list[dict])
def listar_informes(episodio_id: int, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    informes = session.exec(
        select(Informe).where(Informe.episodio_id == episodio_id).order_by(Informe.version)
    ).all()
    return [_serializar(i) for i in informes]


@router.post("/{episodio_id}/finalizar")
def finalizar_episodio(episodio_id: int, session: Session = Depends(get_session)):
    # Supuesto: EpisodioAtencion posee el atributo "estado".
    episodio = session.get(EpisodioAtencion, episodio_id)
    if episodio is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    episodio.estado = "FINALIZADO"
    session.add(episodio)
    session.commit()
    session.refresh(episodio)
    return episodio.model_dump(mode="json")
