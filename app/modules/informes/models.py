from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Informe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episodio_id: int = Field(foreign_key="episodio_atencion.id")
    tipo_informe: str
    contenido_json: str
    fecha_hora: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    estado: str = "GENERADO"
    version: int = 1