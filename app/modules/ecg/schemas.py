import math
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, Field, model_validator


IdentificadorPositivo = Annotated[int, Field(strict=True, gt=0)]
FrecuenciaMuestreoPositiva = Annotated[int, Field(strict=True, gt=0)]
FRECUENCIA_SENSOR_HZ = 250
DURACION_CAPTURA_SENSOR_SEGUNDOS = 10
MUESTRAS_CAPTURA_SENSOR = (
    FRECUENCIA_SENSOR_HZ * DURACION_CAPTURA_SENSOR_SEGUNDOS
)
MAX_MUESTRAS_ECG = MUESTRAS_CAPTURA_SENSOR


def _validar_muestras(valor: object) -> list[float]:
    if not isinstance(valor, list) or not valor:
        raise ValueError("muestras debe ser una lista no vacía")
    if len(valor) > MAX_MUESTRAS_ECG:
        raise ValueError(f"muestras no puede superar {MAX_MUESTRAS_ECG} elementos")

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

    @model_validator(mode="after")
    def validar_muestras_adc(self) -> Self:
        if self.unidad == "ADC" and any(
            not muestra.is_integer() or not 0 <= muestra <= 4095
            for muestra in self.muestras
        ):
            raise ValueError("las muestras ADC deben ser enteros entre 0 y 4095")
        return self


class EntradaECG(BaseModel):
    episodio_id: IdentificadorPositivo
    dispositivo_id: IdentificadorPositivo
    origen: Literal["SENSOR", "SIMULADOR"]
    data: DatosECG

    @model_validator(mode="after")
    def validar_captura_sensor(self) -> Self:
        if self.origen == "SENSOR":
            if self.data.adquisicion_id is None:
                raise ValueError("la captura del sensor requiere adquisicion_id")
            if self.data.frecuencia_muestreo_hz != FRECUENCIA_SENSOR_HZ:
                raise ValueError(
                    f"la frecuencia del sensor debe ser {FRECUENCIA_SENSOR_HZ} Hz"
                )
            if self.data.unidad != "ADC":
                raise ValueError("la captura del sensor debe conservar la unidad ADC")
            if len(self.data.muestras) != MUESTRAS_CAPTURA_SENSOR:
                raise ValueError(
                    f"la captura del sensor debe contener exactamente "
                    f"{MUESTRAS_CAPTURA_SENSOR} muestras"
                )
        return self


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
