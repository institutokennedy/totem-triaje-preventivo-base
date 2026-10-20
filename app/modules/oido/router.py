import json
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Dispositivo, EpisodioAtencion, ResultadoModulo
from app.modules.oido.schemas import ResultadoOidoCreate, RespuestaJoystickCreate

router = APIRouter(prefix="/api/v1/oido", tags=["oido"])
pages_router = APIRouter(tags=["oido-paginas"])

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[2] / "templates")
)

MODULO = "oido"

# --- Respuestas del joystick (ESP32 -> navegador) ---------------------------
# Buffer en memoria: el ESP32 publica cada respuesta y el navegador la consulta
# por sondeo. Requiere un solo proceso de uvicorn (sin --workers > 1).
MAX_RESPUESTAS_POR_DISPOSITIVO = 200
_lock = threading.Lock()
_respuestas: dict[int, deque] = {}
_secuencia = 0


def limpiar_respuestas() -> None:
    """Vacía el buffer (útil en pruebas)."""
    global _secuencia
    with _lock:
        _respuestas.clear()
        _secuencia = 0


@pages_router.get("/oido", include_in_schema=False)
def pagina_oido(request: Request, episodio_id: int | None = None):
    return templates.TemplateResponse(
        request,
        "oido/oido.html",
        {"episodio_id": episodio_id if episodio_id is not None else ""},
    )


def _serializar(registro: ResultadoModulo) -> dict:
    salida = registro.model_dump()
    try:
        datos = json.loads(registro.data_json)
    except (TypeError, ValueError):
        datos = registro.data_json
    if isinstance(datos, dict):
        salida["origen"] = datos.pop("_origen", None)
    salida["data_json"] = datos
    return salida


@router.post("/resultados", status_code=status.HTTP_201_CREATED)
def crear_resultado_oido(payload: ResultadoOidoCreate, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, payload.episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    if session.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    datos = payload.data.model_dump(exclude_none=True)
    datos["_origen"] = payload.origen
    registro = ResultadoModulo(
        episodio_id=payload.episodio_id,
        dispositivo_id=payload.dispositivo_id,
        modulo=MODULO,
        data_json=json.dumps(datos),
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return _serializar(registro)


@router.get("/resultados/{episodio_id}", response_model=List[dict])
def listar_resultados_oido(episodio_id: int, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    registros = session.exec(
        select(ResultadoModulo).where(
            ResultadoModulo.episodio_id == episodio_id,
            ResultadoModulo.modulo == MODULO,
        )
    ).all()
    return [_serializar(r) for r in registros]


@router.post("/respuestas", status_code=status.HTTP_201_CREATED)
def publicar_respuesta(payload: RespuestaJoystickCreate, session: Session = Depends(get_session)):
    """Recibe una respuesta del joystick (arriba = True / abajo = False)."""
    global _secuencia
    if session.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    with _lock:
        _secuencia += 1
        entrada = {
            "seq": _secuencia,
            "dispositivo_id": payload.dispositivo_id,
            "respuesta": payload.respuesta,
            "origen": payload.origen,
            "recibida_en": datetime.now().isoformat(),
        }
        cola = _respuestas.setdefault(
            payload.dispositivo_id, deque(maxlen=MAX_RESPUESTAS_POR_DISPOSITIVO)
        )
        cola.append(entrada)
    return entrada


@router.get("/respuestas/{dispositivo_id}")
def consultar_respuestas(dispositivo_id: int, despues_de: int = 0):
    """Devuelve las respuestas con seq > despues_de y el último número de secuencia global."""
    with _lock:
        nuevas = [r for r in _respuestas.get(dispositivo_id, ()) if r["seq"] > despues_de]
        ultimo = _secuencia
    return {"ultimo": ultimo, "respuestas": nuevas}