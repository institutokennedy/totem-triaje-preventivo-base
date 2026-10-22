"""AplicaciÃ³n aislada para previsualizar el frontend ECG con el simulador Python.

Sirve la misma pantalla ECG que la aplicación principal y reutiliza las rutas del router ECG.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.modules.ecg.router import router as ecg_router


APP_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = APP_DIR / "templates" / "modulos" / "ecg.html"

app = FastAPI(
    title="PrevisualizaciÃ³n aislada del frontend ECG",
    description="DemostraciÃ³n tÃ©cnica; no persiste resultados.",
)
app.include_router(ecg_router)


@app.get("/", include_in_schema=False)
def pagina_ecg() -> FileResponse:
    return FileResponse(TEMPLATE_PATH, media_type="text/html")

