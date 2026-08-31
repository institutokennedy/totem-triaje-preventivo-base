from datetime import datetime

from pydantic import BaseModel


class DatosAmbiente(BaseModel):
    temperatura_c: float
    humedad_porcentaje: float


class EntradaAmbiente(BaseModel):
    episodio_id: int
    dispositivo_id: int
    origen: str
    data: DatosAmbiente


class RespuestaGuardado(BaseModel):
    mensaje: str
    resultado_id: int


class ResultadoAmbiente(BaseModel):
    id: int
    data: DatosAmbiente


class RespuestaConsulta(BaseModel):
    episodio_id: int
    modulo: str
    resultados: list[ResultadoAmbiente]


class ResultadoAmbienteCompleto(BaseModel):
    id: int
    episodio_id: int
    dispositivo_id: int
    data: DatosAmbiente
    fecha_hora: datetime