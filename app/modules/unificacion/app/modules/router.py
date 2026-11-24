from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlmodel import Session

from app.core.database import get_session

from . import services
router = APIRouter(tags=["unificacion"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent))
templates.env.loader = ChoiceLoader(
    [
        templates.env.loader,
        FileSystemLoader(str(Path(__file__).resolve().parents[4] / "templates")),
    ]
)


@router.get(
    "/api/v1/episodios/{episodio_id}/trazabilidad",
)
def trazabilidad(episodio_id: int, session: Session = Depends(get_session)):
    return services.obtener_trazabilidad_episodio(session, episodio_id)


@router.get(
    "/unificacion/episodios/{episodio_id}/resumen",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def pagina_resumen(request: Request, episodio_id: int):
    return templates.TemplateResponse(
        request, "resumen.html", {"episodio_id": episodio_id}
    )


@router.get(
    "/unificacion/resumen.js",
    name="unificacion_resumen_js",
    include_in_schema=False,
)
def resumen_js():
    return FileResponse(
        Path(__file__).resolve().with_name("resumen.js"),
        media_type="application/javascript",
    )