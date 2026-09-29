from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Informe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episodio_id: int = Field(foreign_key="episodioatencion.id_episodio")
    tipo_informe: str
    contenido_json: str
    fecha_hora: datetime = Field(default_factory=datetime.utcnow)
    estado: str = "GENERADO"
    version: int = 1
    