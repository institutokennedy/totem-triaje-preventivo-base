from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConsentimientoCreate(BaseModel):
    """Esquema de entrada para registrar el consentimiento."""

    episodio_id: int = Field(..., gt=0)
    version: str = Field(..., min_length=1)
    aceptado: bool = Field(...)
    observacion: Optional[str] = Field(None)


class ConsentimientoResponse(BaseModel):
    """Esquema de respuesta para las consultas de consentimiento."""

    id: int
    episodio_id: int
    version: str
    aceptado: bool
    observacion: Optional[str] = None
    fecha_hora: datetime