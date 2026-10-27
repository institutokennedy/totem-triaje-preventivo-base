from typing import List, Literal

from pydantic import BaseModel, StrictBool, StrictInt, model_validator

LadoOido = Literal["IZQUIERDO", "DERECHO"]
RespuestaOido = Literal["IZQUIERDO", "DERECHO", "NO_ESCUCHE"]


class CuestionarioOido(BaseModel):
    tiene_problema_auditivo: StrictBool
    problemas_auditivos: list[str]
    otro_problema: str
    factores: list[str]


class EnsayoOido(BaseModel):
    frecuencia_hz: StrictInt
    lado_estimulo: LadoOido
    respuesta: RespuestaOido

    @model_validator(mode="after")
    def validar_frecuencia(self) -> "EnsayoOido":
        if self.frecuencia_hz <= 0:
            raise ValueError("La frecuencia debe ser un entero estrictamente mayor a 0")
        return self


class DatosOido(BaseModel):
    frecuencias_hz: List[StrictInt] | None = None
    resultados_oido_derecho: List[StrictBool] | None = None
    resultados_oido_izquierdo: List[StrictBool] | None = None
    ensayos: list[EnsayoOido] | None = None
    nivel_senal: Literal["NORMAL", "REDUCIDO_POR_AUTOINFORME"] = "NORMAL"
    cuestionario: CuestionarioOido | None = None

    @model_validator(mode="after")
    def validar_listas(self) -> "DatosOido":
        campos_legacy = (
            self.frecuencias_hz,
            self.resultados_oido_derecho,
            self.resultados_oido_izquierdo,
        )
        usa_formato_legacy = any(campo is not None for campo in campos_legacy)

        if self.ensayos is not None:
            if not self.ensayos:
                raise ValueError("ensayos debe contener al menos un elemento")
            if usa_formato_legacy:
                raise ValueError("No se pueden mezclar ensayos con resultados del formato anterior")
            return self

        if not usa_formato_legacy:
            raise ValueError("Debe proporcionar ensayos o resultados del formato anterior")
        if any(campo is None for campo in campos_legacy):
            raise ValueError(
                "frecuencias_hz y los resultados de ambos oídos son obligatorios"
            )
        assert self.frecuencias_hz is not None
        assert self.resultados_oido_derecho is not None
        assert self.resultados_oido_izquierdo is not None
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


class RespuestaJoystickCreate(BaseModel):
    """Respuesta individual del joystick; bool se conserva por compatibilidad."""

    dispositivo_id: int
    respuesta: StrictBool | RespuestaOido
    origen: str = "ESP32"