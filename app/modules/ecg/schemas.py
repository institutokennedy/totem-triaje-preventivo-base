import math
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field


IdentificadorPositivo = Annotated[int, Field(strict=True, gt=0)]
FrecuenciaMuestreoPositiva = Annotated[int, Field(strict=True, gt=0)]


def _validar_muestras(valor: object) -> list[float]:
    if not isinstance(valor, list) or not valor:
        raise ValueError("muestras debe ser una lista no vacía")

    muestras: list[float] = []
    for muestra in valor:
        if isinstance(muestra, bool) or not isinstance(muestra, (int, float)):
            raise ValueError("cada muestra debe ser un número")
        try:
            muestra_float = float(muestra)
        except OverflowError as error:
            raise ValueError("cada muestra debe ser un número finito") from error
        if not math.isfinite(muestra_float):
            raise ValueError("cada muestra debe ser un número finito")
        muestras.append(muestra_float)

    return muestras


MuestrasECG = Annotated[list[float], BeforeValidator(_validar_muestras)]


class DatosECG(BaseModel):
    frecuencia_muestreo_hz: FrecuenciaMuestreoPositiva
    muestras: MuestrasECG
    unidad: Literal["mV", "ADC"]
    adquisicion_id: UUID | None = None


class EntradaECG(BaseModel):
    episodio_id: IdentificadorPositivo
    dispositivo_id: IdentificadorPositivo
    origen: Literal["SENSOR", "SIMULADOR"]
    data: DatosECG


class RespuestaGuardado(BaseModel):
    mensaje: str
    resultado_id: IdentificadorPositivo


class ResultadoECG(BaseModel):
    id: IdentificadorPositivo
    data: DatosECG


class RespuestaConsulta(BaseModel):
    episodio_id: IdentificadorPositivo
    modulo: str
    resultados: list[ResultadoECG]
