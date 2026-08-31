from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


def build_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Construye un motor SQLite apto para FastAPI y activa claves foráneas."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    db_engine = create_engine(database_url, echo=echo, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(db_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return db_engine


engine = build_engine(settings.database_url, echo=settings.database_echo)


def _ensure_default_data_directory() -> None:
    if settings.database_url.startswith("sqlite"):
        Path(__file__).resolve().parents[2].joinpath("data").mkdir(exist_ok=True)


def create_db_and_tables(db_engine: Engine | None = None) -> None:
    """Registra todos los modelos y crea únicamente las tablas faltantes."""
    _ensure_default_data_directory()
    import app.models  # noqa: F401: carga los modelos en metadata

    SQLModel.metadata.create_all(db_engine or engine)


def get_session() -> Generator[Session, None, None]:
    """Dependencia compartida: una sesión por solicitud HTTP."""
    with Session(engine) as session:
        yield session

