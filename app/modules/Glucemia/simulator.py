import random
from typing import Literal
from .schemas import DatosGlucemia


def generar_lectura_simulada(
    unidad: Literal["mg/dL", "mmol/L"] = "mg/dL"
) -> DatosGlucemia:
    """Genera una lectura ficticia de glucemia para pruebas de software."""
    if unidad == "mmol/L":
        valor = round(random.uniform(4.4, 7.8), 1)
    else:
        valor = round(random.uniform(80.0, 140.0), 1)

    return DatosGlucemia(valor=valor, unidad=unidad, metodo="SIMULADO")