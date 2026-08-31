
from datetime import date, datetime

from pydantic import BaseModel


class PacienteCrear(BaseModel):
    dni: str
    nombre: str
    apellido: str
    fecha_nacimiento: date
    email: str | None = None
    telefono: str | None = None


class PacienteRespuesta(BaseModel):
    id: int
    dni: str
    nombre: str
    apellido: str
    fecha_nacimiento: date
    email: str | None
    telefono: str | None
    creado_en: datetime