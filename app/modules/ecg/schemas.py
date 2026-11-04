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


def _validar_muestras_mv_out(valor: object) -> list[int]:
    if not isinstance(valor, list) or not valor:
        raise ValueError("muestras_mV_OUT debe ser una lista no vacía")
    if len(valor) > MAX_MUESTRAS_ECG:
        raise ValueError(
            f"muestras_mV_OUT no puede superar {MAX_MUESTRAS_ECG} elementos"
        )
    if any(
        isinstance(muestra, bool)
        or not isinstance(muestra, int)
        or muestra < 0
        for muestra in valor
    ):
        raise ValueError("cada muestra mV_OUT debe ser un entero no negativo")
    return valor


MuestrasMvOutECG = Annotated[list[int], BeforeValidator(_validar_muestras_mv_out)]


class MetadatosCalibracionADCECG(BaseModel):
    estado: Literal["CALIBRADA", "ERROR", "NO_CONFIABLE"]
    metodo: Literal["ESP_IDF_LINE_FITTING"]
    fuente: Literal[
        "EFUSE_VREF",
        "EFUSE_TWO_POINT",
        "DEFAULT_VREF",
        "NO_DISPONIBLE",
    ]
    vref_efuse_raw: int | None = None
    vref_efuse_mv: int | None = None
    adc_unit: Literal["ADC1"]
    gpio: Literal[34]
    canal: Literal[6]
    resolucion_bits: Literal[12]
    atenuacion: Literal["ADC_11db/ADC_ATTEN_DB_12"]
    chip_model: str = Field(min_length=1)
    chip_revision: int = Field(strict=True, gt=0)
    esp_idf_version: str = Field(min_length=1)
    error_codigo: int | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validar_estado_calibracion(self) -> Self:
        if self.estado == "CALIBRADA":
            if (
                self.fuente != "EFUSE_VREF"
                or self.vref_efuse_raw != 17
                or self.vref_efuse_mv != 1093
                or self.chip_model != "ESP32-D0WD-V3"
                or self.chip_revision != 301
                or self.esp_idf_version != "v5.5.5"
                or self.error_codigo is not None
                or self.error not in (None, "")
            ):
                raise ValueError(
                    "la calibración debe corresponder al eFuse Vref verificado"
                )
        elif self.estado == "ERROR" and (
            self.error_codigo in (None, 0)
            or not self.error
            or self.error.strip() == ""
        ):
            raise ValueError(
                "un error de calibración requiere código y motivo explícitos"
            )
        elif self.estado == "NO_CONFIABLE" and (
            self.error_codigo is not None
            or not self.error
            or self.error.strip() == ""
        ):
            raise ValueError(
                "una calibración no confiable requiere un motivo explícito"
            )
        return self


class DatosECG(BaseModel):
    frecuencia_muestreo_hz: FrecuenciaMuestreoPositiva
    muestras: MuestrasECG
    unidad: Literal["mV", "ADC"]
    adquisicion_id: UUID | None = None
    muestras_mV_OUT: MuestrasMvOutECG | None = None
    calibracion_adc: MetadatosCalibracionADCECG | None = None
    estado_mV_OUT: Literal["NO_CONFIABLE", "NO_EVALUABLE"] | None = None

    @model_validator(mode="after")
    def validar_muestras_y_calibracion(self) -> Self:
        if self.unidad == "ADC" and any(
            not muestra.is_integer() or not 0 <= muestra <= 4095
            for muestra in self.muestras
        ):
            raise ValueError("las muestras ADC deben ser enteros entre 0 y 4095")
        if self.muestras_mV_OUT is not None:
            if self.unidad != "ADC":
                raise ValueError("mV_OUT requiere conservar las muestras originales ADC")
            if len(self.muestras_mV_OUT) != len(self.muestras):
                raise ValueError("muestras_mV_OUT debe corresponder a cada muestra ADC")
            if self.estado_mV_OUT == "NO_EVALUABLE":
                raise ValueError("mV_OUT con muestras no puede ser NO_EVALUABLE")
            if self.estado_mV_OUT != "NO_CONFIABLE" and (
                self.calibracion_adc is None
                or self.calibracion_adc.estado != "CALIBRADA"
            ):
                raise ValueError("mV_OUT requiere calibración ADC verificada")
        if (
            self.calibracion_adc is not None
            and self.calibracion_adc.estado == "CALIBRADA"
            and self.muestras_mV_OUT is None
            and self.estado_mV_OUT is None
        ):
            raise ValueError("la calibración exitosa requiere muestras mV_OUT")
        if (
            self.calibracion_adc is not None
            and self.calibracion_adc.estado == "ERROR"
            and self.muestras_mV_OUT is not None
        ):
            raise ValueError("no se aceptan mV_OUT cuando falló la calibración")
        if (
            self.calibracion_adc is not None
            and self.calibracion_adc.estado == "NO_CONFIABLE"
            and self.estado_mV_OUT is None
        ):
            raise ValueError(
                "una calibración no confiable requiere estado_mV_OUT explícito"
            )
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


class DatosTecnicosEvaluacionECG(BaseModel):
    frecuencia_muestreo_hz: int
    cantidad_muestras: int
    unidad: Literal["mV", "ADC"]


class MetricasTecnicasSenalECG(BaseModel):
    duracion_entre_muestras_segundos: float
    amplitud_minima: float
    amplitud_maxima: float
    amplitud_rango: float
    muestras_distintas: int
    muestras_adc_en_riel_inferior: int | None = None
    muestras_adc_en_riel_superior: int | None = None


NivelEvaluacionPreventiva = Literal[
    "VERDE", "AMARILLO", "ROJO", "NO_EVALUABLE"
]
ColorEvaluacionPreventiva = Literal["VERDE", "AMARILLO", "ROJO", "GRIS"]
EstadoReglaClinicaECG = Literal["CUMPLE", "NO_CUMPLE", "NO_EVALUABLE"]
IdentificadorReglaClinicaECG = Literal[
    "RC-ECG-001",
    "RC-ECG-002",
    "RC-ECG-003",
    "RC-ECG-004",
    "RC-ECG-005",
    "RC-ECG-006",
    "RC-ECG-007",
    "RC-ECG-008",
    "RC-ECG-009",
]
IDENTIFICADORES_REGLAS_ECG = (
    "RC-ECG-001",
    "RC-ECG-002",
    "RC-ECG-003",
    "RC-ECG-004",
    "RC-ECG-005",
    "RC-ECG-006",
    "RC-ECG-007",
    "RC-ECG-008",
    "RC-ECG-009",
)
CALIDAD_SENAL_APTA = "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA"


class ResultadoReglaClinicaECG(BaseModel):
    identificador: IdentificadorReglaClinicaECG
    estado: EstadoReglaClinicaECG
    motivo: str = Field(min_length=1)
    valores_medidos: dict[str, float] = Field(default_factory=dict)


class EvaluacionPreventivaECG(BaseModel):
    nivel: NivelEvaluacionPreventiva
    color: ColorEvaluacionPreventiva
    motivo: str = Field(min_length=1)
    parametros_evaluados: list[str]
    valores_medidos: dict[str, float]
    criterios_activados: list[str]
    parametros_no_evaluables: list[str]
    calidad_senal: str = Field(min_length=1)
    datos_tecnicos: DatosTecnicosEvaluacionECG
    metricas_tecnicas: MetricasTecnicasSenalECG | None = None
    advertencias_tecnicas: list[str]
    reglas: list[ResultadoReglaClinicaECG] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_estado_preventivo(self) -> Self:
        colores_por_nivel = {
            "VERDE": "VERDE",
            "AMARILLO": "AMARILLO",
            "ROJO": "ROJO",
            "NO_EVALUABLE": "GRIS",
        }
        if self.color != colores_por_nivel[self.nivel]:
            raise ValueError("el color no coincide con el nivel preventivo")
        if self.nivel == "VERDE":
            identificadores = [regla.identificador for regla in self.reglas]
            if (
                len(identificadores) != len(IDENTIFICADORES_REGLAS_ECG)
                or set(identificadores) != set(IDENTIFICADORES_REGLAS_ECG)
                or any(regla.estado != "CUMPLE" for regla in self.reglas)
                or any(not regla.valores_medidos for regla in self.reglas)
            ):
                raise ValueError(
                    "el nivel VERDE requiere las nueve reglas, todas en estado CUMPLE"
                )
            if (
                self.calidad_senal != CALIDAD_SENAL_APTA
                or self.parametros_evaluados != list(IDENTIFICADORES_REGLAS_ECG)
                or self.parametros_no_evaluables
                or self.criterios_activados
                or not self.valores_medidos
                or any(
                    not any(
                        nombre.startswith(f"{identificador}.")
                        for nombre in self.valores_medidos
                    )
                    for identificador in IDENTIFICADORES_REGLAS_ECG
                )
            ):
                raise ValueError(
                    "el nivel VERDE requiere calidad apta y una evaluación completa"
                )
            if (
                self.datos_tecnicos.frecuencia_muestreo_hz < 500
                or (
                    self.datos_tecnicos.cantidad_muestras - 1
                )
                / self.datos_tecnicos.frecuencia_muestreo_hz < 10
                or self.datos_tecnicos.unidad != "mV"
            ):
                raise ValueError(
                    "el nivel VERDE requiere al menos 500 Hz, 10 segundos "
                    "continuos y amplitud en mV"
                )
        return self


class ResultadoECG(BaseModel):
    id: IdentificadorPositivo
    data: DatosECG
    evaluacion_preventiva: EvaluacionPreventivaECG


class RespuestaConsulta(BaseModel):
    episodio_id: IdentificadorPositivo
    modulo: str
    resultados: list[ResultadoECG]
