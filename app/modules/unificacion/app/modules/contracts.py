from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ORIGENES_RESULTADO = Literal["SENSOR", "SIMULADOR"]

SLUGS_MODULOS = {
    "signos_vitales": "signos-vitales",
    "ecg": "ecg",
    "glucemia": "glucemia",
    "boca": "boca",
    "vista": "vista",
    "oido": "oido",
}

MODULOS_REQUERIDOS = tuple(SLUGS_MODULOS)

RUTAS_RESULTADOS = {
    modulo: f"/api/v1/{slug}/resultados"
    for modulo, slug in SLUGS_MODULOS.items()
}

RUTAS_CONSULTA_RESULTADOS = {
    modulo: f"{ruta}/{{episodio_id}}"
    for modulo, ruta in RUTAS_RESULTADOS.items()
}


class DatosModulo(BaseModel):
    model_config = ConfigDict(extra="allow")


class DatosSignosVitales(DatosModulo):
    presion_sistolica: float
    presion_diastolica: float
    frecuencia_cardiaca: float
    temperatura: float
    saturacion_oxigeno: float


class DatosECG(DatosModulo):
    frecuencia_muestreo_hz: int
    muestras: list[float]
    unidad: Literal["mV", "ADC"]


class DatosGlucemia(DatosModulo):
    valor: float
    unidad: Literal["mg/dL", "mmol/L"]
    metodo: str = Field(min_length=1)


class DatosBoca(DatosModulo):
    nombre_imagen: str = Field(min_length=1)
    observacion_tecnica: str | None = None


class DatosVista(DatosModulo):
    prueba: str = Field(min_length=1)
    ojo_derecho: str = Field(min_length=1)
    ojo_izquierdo: str = Field(min_length=1)
    distancia_cm: float = Field(gt=0)


class DatosOido(DatosModulo):
    frecuencias_hz: list[int]
    resultados_oido_derecho: list[bool]
    resultados_oido_izquierdo: list[bool]


class ResultadoModuloBase(BaseModel):
    episodio_id: int = Field(gt=0)
    dispositivo_id: int = Field(gt=0)
    origen: ORIGENES_RESULTADO


class ResultadoSignosVitalesCreate(ResultadoModuloBase):
    data: DatosSignosVitales


class ResultadoECGCreate(ResultadoModuloBase):
    data: DatosECG


class ResultadoGlucemiaCreate(ResultadoModuloBase):
    data: DatosGlucemia


class ResultadoBocaCreate(ResultadoModuloBase):
    data: DatosBoca


class ResultadoVistaCreate(ResultadoModuloBase):
    data: DatosVista


class ResultadoOidoCreate(ResultadoModuloBase):
    data: DatosOido


CONTRATOS_RESULTADOS = {
    "signos_vitales": {
        "post": RUTAS_RESULTADOS["signos_vitales"],
        "get": RUTAS_CONSULTA_RESULTADOS["signos_vitales"],
        "campos": tuple(DatosSignosVitales.model_fields),
        "schema": ResultadoSignosVitalesCreate,
    },
    "ecg": {
        "post": RUTAS_RESULTADOS["ecg"],
        "get": RUTAS_CONSULTA_RESULTADOS["ecg"],
        "campos": tuple(DatosECG.model_fields),
        "schema": ResultadoECGCreate,
    },
    "glucemia": {
        "post": RUTAS_RESULTADOS["glucemia"],
        "get": RUTAS_CONSULTA_RESULTADOS["glucemia"],
        "campos": tuple(DatosGlucemia.model_fields),
        "schema": ResultadoGlucemiaCreate,
    },
    "boca": {
        "post": RUTAS_RESULTADOS["boca"],
        "get": RUTAS_CONSULTA_RESULTADOS["boca"],
        "campos": tuple(DatosBoca.model_fields),
        "schema": ResultadoBocaCreate,
    },
    "vista": {
        "post": RUTAS_RESULTADOS["vista"],
        "get": RUTAS_CONSULTA_RESULTADOS["vista"],
        "campos": tuple(DatosVista.model_fields),
        "schema": ResultadoVistaCreate,
    },
    "oido": {
        "post": RUTAS_RESULTADOS["oido"],
        "get": RUTAS_CONSULTA_RESULTADOS["oido"],
        "campos": tuple(DatosOido.model_fields),
        "schema": ResultadoOidoCreate,
    },
}
