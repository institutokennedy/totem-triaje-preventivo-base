import math
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class DatosGlucemia(BaseModel):
    """Estructura interna del objeto 'data' para glucemia."""

    valor: float = Field(..., description="Valor numérico de la medición")
    unidad: Literal["mg/dL", "mmol/L"] = Field(
        ..., description="Unidad técnica acordada"
    )
    metodo: str = Field(
        ..., min_length=1, description="Método de captura declarado"
    )

    @field_validator("valor")
    @classmethod
    def validar_valor_finito(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("El valor de glucemia debe ser un número finito.")
        if v < 0:
            raise ValueError("El valor de glucemia no puede ser negativo.")
        return v


class ResultadoGlucemiaCreate(BaseModel):
    """Contrato común de entrada POST para glucemia."""

    episodio_id: int = Field(..., gt=0)
    dispositivo_id: int = Field(..., gt=0)
    origen: Literal["SENSOR", "SIMULADOR"]
    data: DatosGlucemia