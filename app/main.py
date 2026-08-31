from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import create_db_and_tables

from app.modules.pacientes.router import router as pacientes_router
from app.modules.episodios.router import router as episodios_router
from app.modules.dispositivos.router import router as dispositivos_router
from app.modules.demo_ambiente.router import router as demo_ambiente_router


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
            "Permite registrar pacientes, episodios, dispositivos y resultados "
            "ficticios del módulo de demostración."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    @application.get(
        "/health",
        tags=["Sistema"],
        summary="Verificar la API",
    )
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

    return application


app = create_app()