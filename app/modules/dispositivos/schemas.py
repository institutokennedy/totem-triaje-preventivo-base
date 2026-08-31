from datetime import datetime

from pydantic import BaseModel


class DispositivoRespuesta(BaseModel):
    id: int
    codigo: str
    nombre: str
    tipo: str
    estado: str
    activo: bool
    creado_en: datetime