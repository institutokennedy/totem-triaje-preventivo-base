from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.common.models import EpisodioAtencion
from app.common.resultado_service import (
    consultar_resultados,
    guardar_resultado,
)
from app.core.database import get_session
from app.modules.ecg.schemas import (
    DatosECG,
    EntradaECG,
    RespuestaConsulta,
    RespuestaGuardado,
)


MODULO = "ecg"
APP_DIR = FilePath(__file__).resolve().parents[2]


router = APIRouter(
    prefix="/api/v1/ecg",
    tags=["ECG"],
)


@router.get("/pantalla", include_in_schema=False)
def pagina_ecg() -> FileResponse:
    """Sirve la pantalla de captura desde la aplicación principal."""
    return FileResponse(
        APP_DIR / "templates" / "modulos" / "ecg.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/frontend.js", include_in_schema=False)
def frontend_ecg() -> FileResponse:
    """Sirve el JavaScript del módulo sin requerir un mount estático global."""
    return FileResponse(
        APP_DIR / "static" / "js" / "ecg.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/circuito/pantalla", include_in_schema=False)
def pagina_circuito() -> FileResponse:
    """Sirve la pantalla transversal de selección de circuito del Grupo 2."""
    return FileResponse(
        APP_DIR / "templates" / "modulos" / "circuito.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/circuito/prueba", include_in_schema=False)
def pagina_prueba_circuito() -> FileResponse:
    """Sirve una herramienta temporal aislada para probar HU-03 y ECG."""
    return FileResponse(
        APP_DIR / "templates" / "modulos" / "circuito_prueba.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/circuito/frontend.js", include_in_schema=False)
def frontend_circuito() -> FileResponse:
    """Sirve el JavaScript de selección de circuito."""
    return FileResponse(
        APP_DIR / "static" / "js" / "circuito.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/simulador/captura")
def captura_simulada() -> dict[str, int | list[float] | str]:
    """Entrega las muestras técnicas ficticias del simulador ECG."""
    from app.modules.ecg.simulator import generar_datos_ecg

    return DatosECG.model_validate(generar_datos_ecg()).model_dump()

@router.post(
    "/resultados",
    response_model=RespuestaGuardado,
    status_code=201,
)
def recibir_resultado(
    entrada: EntradaECG,
    session: Session = Depends(get_session),
) -> RespuestaGuardado:
    episodio = session.get(EpisodioAtencion, entrada.episodio_id)
    if episodio is None:
        raise HTTPException(status_code=404, detail="El episodio no existe")
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
    "/resultados/{episodio_id}",
    response_model=RespuestaConsulta,
)
def obtener_resultados(
    episodio_id: int = Path(gt=0),
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

# python -m pytest -q -p no:cacheprovider --basetemp=.pytest-temp app/modules/ecg/test_router.py
# python -m uvicorn app.modules.ecg.preview_app:app --reload
# python -m uvicorn app.main:app --reload

# py -3.13 -m venv .venv
