
from datetime import datetime
from pydantic import BaseModel


class TriajeBoca(BaseModel):
    nivel: str
    detalle: str


class ColorimetriaBoca(BaseModel):
    rojo: float
    verde: float
    azul: float


class MetricasBoca(BaseModel):
    nitidez_laplaciano: float
    brillo_promedio: float
    contraste_profundo_porcentaje: float
    colorimetria_rgb: ColorimetriaBoca


class DatosBoca(BaseModel):
    sistema: str
    timestamp: str
    triaje: TriajeBoca
    metricas_tecnicas: MetricasBoca
    analisis_de_causas: str
    recomendacion: str


class EntradaBoca(BaseModel):
    episodio_id: int
    dispositivo_id: int
    origen: str
    data: DatosBoca


class RespuestaGuardado(BaseModel):
    mensaje: str
    resultado_id: int


class ResultadoBoca(BaseModel):
    id: int
    data: DatosBoca


class RespuestaConsulta(BaseModel):
    episodio_id: int
    modulo: str
    resultados: list[ResultadoBoca]


class ResultadoBocaCompleto(BaseModel):
    id: int
    episodio_id: int
    dispositivo_id: int
    data: DatosBoca
    fecha_hora: datetime
