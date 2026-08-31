from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Paciente(SQLModel, table=True):
    __tablename__ = "paciente"

    id: int | None = Field(default=None, primary_key=True)
    dni: str = Field(index=True, unique=True, min_length=7, max_length=12)
    nombre: str = Field(min_length=1, max_length=80)
    apellido: str = Field(min_length=1, max_length=80)
    fecha_nacimiento: date
    email: str | None = Field(default=None, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    creado_en: datetime = Field(default_factory=utc_now)


class EpisodioAtencion(SQLModel, table=True):
    __tablename__ = "episodio_atencion"

    id: int | None = Field(default=None, primary_key=True)
    paciente_id: int = Field(foreign_key="paciente.id", index=True)
    tipo_circuito: str = Field(max_length=40)
    estado: str = Field(default="INICIADO", max_length=30)
    iniciado_en: datetime = Field(default_factory=utc_now)
    finalizado_en: datetime | None = None


class Dispositivo(SQLModel, table=True):
    __tablename__ = "dispositivo"

    id: int | None = Field(default=None, primary_key=True)
    codigo: str = Field(index=True, unique=True, min_length=1, max_length=40)
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str = Field(min_length=1, max_length=50)
    estado: str = Field(default="DISPONIBLE", max_length=30)
    activo: bool = True
    creado_en: datetime = Field(default_factory=utc_now)


class ResultadoModulo(SQLModel, table=True):
    __tablename__ = "resultado_modulo"

    id: int | None = Field(default=None, primary_key=True)
    episodio_id: int = Field(foreign_key="episodio_atencion.id", index=True)
    dispositivo_id: int = Field(foreign_key="dispositivo.id")
    modulo: str = Field(index=True, max_length=50)
    data_json: str
    fecha_hora: datetime = Field(default_factory=utc_now)
