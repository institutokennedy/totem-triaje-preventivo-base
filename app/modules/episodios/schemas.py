from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EpisodioCrear(BaseModel):
    paciente_id: int
    tipo_circuito: Literal["GUARDIA", "COMPLETO"]


class EpisodioRespuesta(BaseModel):
    id: int
    paciente_id: int
    tipo_circuito: str
    estado: str
    iniciado_en: datetime
    finalizado_en: datetime | None
