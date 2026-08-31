from datetime import datetime

from pydantic import BaseModel


class EpisodioCrear(BaseModel):
    paciente_id: int
    tipo_circuito: str


class EpisodioRespuesta(BaseModel):
    id: int
    paciente_id: int
    tipo_circuito: str
    estado: str
    iniciado_en: datetime
    finalizado_en: datetime | None