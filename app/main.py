from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
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
from app.modules.unificacion.app.modules.router import router as unificacion_router

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
        docs_url=None,
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

    @application.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    def api_docs(request: Request):
        response = get_swagger_ui_html(
            openapi_url=application.openapi_url,
            title=f"{settings.app_name} · API",
            swagger_ui_parameters={
                "deepLinking": True,
                "displayRequestDuration": True,
                "docExpansion": "none",
                "filter": True,
                "tryItOutEnabled": True,
                "defaultModelsExpandDepth": -1,
            },
        )
        stylesheet = request.url_for("static", path="/css/api-docs.css")
        branding = (
            '<header class="api-masthead">'
            '<a class="api-brand" href="/" aria-label="Volver al inicio">'
            '<span class="api-brand-mark" aria-hidden="true">♥</span>'
            '<span><strong>Tótem Preventivo</strong><small>GUÍA DE PRUEBAS PREVENTIVAS</small></span>'
            '</a><nav aria-label="Navegación de la API">'
            '<a href="/">Inicio</a><a href="/health">Estado del servicio</a>'
            '<a href="/openapi.json">OpenAPI JSON</a>'
            '</nav></header>'
            '<main class="api-docs-shell">'
            '<section class="api-intro" aria-labelledby="api-title">'
            '<p class="api-eyebrow">Centro para desarrolladores</p>'
            '<h1 id="api-title">Explorador de API</h1>'
            f'<p>Documentación interactiva de {escape(settings.app_name)}. '
            'Consulta operaciones, revisa respuestas y prueba solicitudes.</p>'
            '<div class="api-intro-meta"><span class="api-live-dot"></span>'
            f'API v{escape(settings.app_version)} · Entorno educativo</div>'
            '</section>'
        )
        html = response.body.decode("utf-8")
        html = html.replace(
            "</head>",
            f'<link rel="stylesheet" href="{stylesheet}"></head>',
            1,
        )
        html = html.replace("<body>", f"<body>{branding}", 1)
        html = html.replace(
            '<div id="swagger-ui"></div>',
            '<section class="api-reference" aria-label="Referencia de endpoints">'
            '<div class="api-reference-heading"><div><p>Referencia</p>'
            '<h2>Endpoints disponibles</h2></div>'
            '<span>Selecciona una operación para ver detalles y probarla</span></div>'
            '<div id="swagger-ui"></div></section></main>',
            1,
        )
        return HTMLResponse(
            content=html,
            status_code=response.status_code,
            headers={"Cache-Control": "no-store"},
        )

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
    application.include_router(unificacion_router)

    return application


app = create_app()
