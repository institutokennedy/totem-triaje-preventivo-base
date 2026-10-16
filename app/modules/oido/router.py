import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Dispositivo, EpisodioAtencion, ResultadoModulo
from app.modules.oido.schemas import ResultadoOidoCreate

router = APIRouter(prefix="/api/v1/oido", tags=["oido"])
pages_router = APIRouter(tags=["oido-paginas"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")

MODULO = "oido"


@pages_router.get("/", include_in_schema=False)
def pagina_inicio():
    return RedirectResponse(url="/oido", status_code=status.HTTP_303_SEE_OTHER)


@pages_router.get("/oido", response_class=HTMLResponse, include_in_schema=False)
def pagina_oido(request: Request, episodio_id: int | None = None):
    return templates.TemplateResponse(
        request=request,
        name="oido/oido.html",
        context={"episodio_id": episodio_id or ""},
    )


@pages_router.get("/resumen", response_class=HTMLResponse, include_in_schema=False)
def pagina_resumen(request: Request, episodio_id: int | None = None):
    return templates.TemplateResponse(
        request=request,
        name="oido/resumen.html",
        context={"episodio_id": episodio_id or ""},
    )


def _serializar(registro: ResultadoModulo) -> dict:
    salida = registro.model_dump(mode="json")
    try:
        salida["data_json"] = json.loads(registro.data_json)
    except (TypeError, ValueError):
        pass
    return salida


@router.post("/resultados", status_code=status.HTTP_201_CREATED)
def crear_resultado_oido(
    payload: ResultadoOidoCreate, session: Session = Depends(get_session)
):
    if session.get(EpisodioAtencion, payload.episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    if session.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    registro = ResultadoModulo(
        episodio_id=payload.episodio_id,
        dispositivo_id=payload.dispositivo_id,
        modulo=MODULO,
        origen=payload.origen,
        data_json=json.dumps(payload.data.model_dump()),
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return _serializar(registro)


@router.get("/resultados/{episodio_id}", response_model=list[dict])
def listar_resultados_oido(episodio_id: int, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    registros = session.exec(
        select(ResultadoModulo).where(
            ResultadoModulo.episodio_id == episodio_id,
            ResultadoModulo.modulo == MODULO,
        )
    ).all()
    return [_serializar(registro) for registro in registros]
