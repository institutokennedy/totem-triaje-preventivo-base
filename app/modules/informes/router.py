import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

# Contrato del repo base: get_session y los modelos comunes se consumen sin modificarse.
from app.core.database import get_session
from app.models import EpisodioAtencion, Paciente, ResultadoModulo
from app.modules.informes.models import Informe
from app.reporte.reporte import LEYENDA, construir_reporte, render_html

router = APIRouter(prefix="/api/v1/episodios", tags=["informes"])

LEYENDA_LEGAL = "Informe preventivo. No constituye un diagnóstico médico."

# Valor de ResultadoModulo.modulo -> nombre visible
MODULOS = {
    "signos_vitales": "Signos vitales",
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
        contenido = json.loads(informe.contenido_json)
    except (TypeError, ValueError):
        contenido = {}
    salida["contenido"] = contenido
    salida["contenido_json"] = contenido
    return salida


def _html_de_informe(informe: Informe) -> str:
    contenido = json.loads(informe.contenido_json)
    return render_html(contenido["reporte"])


def _obtener_informe(session: Session, episodio_id: int, informe_id: int) -> Informe:
    informe = session.get(Informe, informe_id)
    if informe is None or informe.episodio_id != episodio_id:
        raise HTTPException(status_code=404, detail="Informe no encontrado")
    return informe


def _pdf_response(informe: Informe) -> Response:
    html = _html_de_informe(informe)
    try:
        from weasyprint import HTML
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF no disponible. Abra el informe HTML y use Imprimir / Guardar como PDF.",
        )
    pdf = HTML(string=html).write_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="informe_episodio_{informe.episodio_id}_v{informe.version}.pdf"'
            )
        },
    )


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
        "leyenda": LEYENDA,
        "paciente": paciente.model_dump(mode="json"),
        "episodio": episodio.model_dump(mode="json"),
        "modulos_completados": completados,
        "modulos_pendientes": pendientes,
        "resultados": agrupados,
        "generado_en": datetime.now().isoformat(),
        "reporte": construir_reporte(paciente, agrupados, pendientes),
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


@router.get(
    "/{episodio_id}/informes/{informe_id}/html",
    response_class=HTMLResponse,
)
def obtener_informe_html(
    episodio_id: int, informe_id: int, session: Session = Depends(get_session)
):
    informe = _obtener_informe(session, episodio_id, informe_id)
    return HTMLResponse(_html_de_informe(informe))


@router.get("/{episodio_id}/informes/{informe_id}/pdf")
def obtener_informe_pdf(
    episodio_id: int, informe_id: int, session: Session = Depends(get_session)
):
    informe = _obtener_informe(session, episodio_id, informe_id)
    return _pdf_response(informe)


@router.post("/{episodio_id}/cerrar")
@router.post("/{episodio_id}/finalizar")
def finalizar_episodio(episodio_id: int, session: Session = Depends(get_session)):
    episodio = session.get(EpisodioAtencion, episodio_id)
    if episodio is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    episodio.estado = "CERRADO"
    episodio.finalizado_en = datetime.now()
    session.add(episodio)
    session.commit()
    session.refresh(episodio)
    return episodio.model_dump(mode="json")