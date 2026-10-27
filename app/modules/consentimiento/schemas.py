from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConsentimientoCreate(BaseModel):
    """Esquema de entrada para registrar la decisión de consentimiento."""
    episodio_id: int = Field(..., gt=0, description="ID del episodio activo")
    version: str = Field(..., min_length=1, description="Versión del texto del consentimiento (ej: v1.0)")
    aceptado: bool = Field(..., description="True si acepta, False si rechaza")
    observacion: Optional[str] = Field(None, description="Observaciones opcionales")


class ConsentimientoResponse(BaseModel):
    """Esquema de respuesta para las consultas de consentimiento."""
    id: int
    episodio_id: int
    version: str
    aceptado: bool
    observacion: Optional[str] = None
    fecha_hora: datetime