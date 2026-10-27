"""Modelos y contratos compartidos por todos los módulos."""

from app.common.models import Dispositivo, EpisodioAtencion, Paciente, ResultadoModulo

__all__ = [
    "Paciente",
    "EpisodioAtencion",
    "Dispositivo",
    "ResultadoModulo",
]

