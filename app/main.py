from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.core.config import settings
from app.core.database import create_db_and_tables
from app.modules.demo_ambiente.router import router as demo_ambiente_router
from app.modules.dispositivos.router import router as dispositivos_router
from app.modules.episodios.router import router as episodios_router
from app.modules.informes.router import pages_router as informes_pages_router
from app.modules.informes.router import ia_router as informes_ia_router
from app.modules.informes.router import router as informes_router
from app.modules.oido.router import pages_router as oido_pages_router
from app.modules.oido.router import router as oido_router
from app.modules.pacientes.router import router as pacientes_router

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates")
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Crea las tablas al iniciar y luego habilita la aplicación."""
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Base educativa modular para el proyecto Tótem de triaje preventivo. "
            "Permite registrar pacientes, iniciar episodios, consultar dispositivos "
            "y guardar resultados de los módulos."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    application.mount(
        "/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )

    @application.get("/", response_class=HTMLResponse, include_in_schema=False)
    def inicio(request: Request):
        return templates.TemplateResponse(request, "inicio.html")

    @application.get("/health", tags=["Sistema"], summary="Verificar la API")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
        }

    application.include_router(pacientes_router)
    application.include_router(episodios_router)
    application.include_router(dispositivos_router)
    application.include_router(demo_ambiente_router)
    application.include_router(oido_router)
    application.include_router(oido_pages_router)
    application.include_router(informes_router)
    application.include_router(informes_ia_router)
    application.include_router(informes_pages_router)

    return application


app = create_app()
