from sqlmodel import SQLModel, Field

class PacientePrueba(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

print("Modelo correcto")