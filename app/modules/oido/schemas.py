from typing import List

from pydantic import BaseModel, StrictBool, StrictInt, model_validator


class DatosOido(BaseModel):
    frecuencias_hz: List[StrictInt]
    resultados_oido_derecho: List[StrictBool]
    resultados_oido_izquierdo: List[StrictBool]

    @model_validator(mode="after")
    def validar_listas(self) -> "DatosOido":
        n = len(self.frecuencias_hz)
        if n < 1:
            raise ValueError("frecuencias_hz debe contener al menos un elemento")
        if len(self.resultados_oido_derecho) != n or len(self.resultados_oido_izquierdo) != n:
            raise ValueError(
                "frecuencias_hz, resultados_oido_derecho y resultados_oido_izquierdo "
                "deben tener la misma longitud"
            )
        if any(f <= 0 for f in self.frecuencias_hz):
            raise ValueError("Las frecuencias deben ser enteros estrictamente mayores a 0")
        return self


class ResultadoOidoCreate(BaseModel):
    episodio_id: int
    dispositivo_id: int
    origen: str
    data: DatosOido