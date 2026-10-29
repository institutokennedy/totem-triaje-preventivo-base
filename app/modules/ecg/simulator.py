"""Generación de señales sintéticas para pruebas técnicas del módulo ECG.

Las formas de onda de este módulo son esquemáticas y no representan registros
fisiológicos ni sirven para validar mediciones o reglas clínicas.
"""

import math
import random


FRECUENCIA_MUESTREO_HZ = 250
DURACION_PREDETERMINADA_SEGUNDOS = 10


def _es_numero_finito(valor: int | float) -> bool:
    try:
        return math.isfinite(valor)
    except OverflowError:
        return False


def generar_datos_ecg(
    frecuencia_cardiaca_bpm: int = 75,
    duracion_segundos: int | float = DURACION_PREDETERMINADA_SEGUNDOS,
    ritmo: str = "regular",
    semilla: int = 0,
    ruido_amplitud: int | float = 0.0,
    artefacto_sintetico: bool = False,
    onda_p_visible: bool = True,
) -> dict[str, int | list[float] | str]:
    """Devuelve datos ECG ficticios reproducibles con el esquema vigente.

    ``frecuencia_cardiaca_bpm``, duración, ritmo y semilla son controles para
    preparar casos de prueba técnica. El ritmo irregular altera los intervalos
    entre complejos sintéticos; no representa ni identifica una arritmia.
    Ruido y artefacto son perturbaciones reproducibles, no detectores clínicos.
    """
    if (
        isinstance(frecuencia_cardiaca_bpm, bool)
        or not isinstance(frecuencia_cardiaca_bpm, int)
        or frecuencia_cardiaca_bpm <= 0
    ):
        raise ValueError("frecuencia_cardiaca_bpm debe ser un entero positivo")
    if (
        isinstance(duracion_segundos, bool)
        or not isinstance(duracion_segundos, (int, float))
        or not _es_numero_finito(duracion_segundos)
        or duracion_segundos <= 0
    ):
        raise ValueError("duracion_segundos debe ser un número finito positivo")
    if not isinstance(ritmo, str) or ritmo not in {"regular", "irregular"}:
        raise ValueError("ritmo debe ser 'regular' o 'irregular'")
    if isinstance(semilla, bool) or not isinstance(semilla, int):
        raise ValueError("semilla debe ser un entero")
    if (
        isinstance(ruido_amplitud, bool)
        or not isinstance(ruido_amplitud, (int, float))
        or not _es_numero_finito(ruido_amplitud)
        or ruido_amplitud < 0
    ):
        raise ValueError("ruido_amplitud debe ser un número finito no negativo")
    if not isinstance(artefacto_sintetico, bool):
        raise ValueError("artefacto_sintetico debe ser booleano")
    if not isinstance(onda_p_visible, bool):
        raise ValueError("onda_p_visible debe ser booleano")

    try:
        numero_muestras = round(duracion_segundos * FRECUENCIA_MUESTREO_HZ)
    except OverflowError as error:
        raise ValueError("duracion_segundos es demasiado grande para generar") from error
    if numero_muestras < 1:
        raise ValueError("la duración debe producir al menos una muestra")

    generador = random.Random(semilla)
    intervalo_base = 60.0 / frecuencia_cardiaca_bpm
    cantidad_intervalos = math.ceil(duracion_segundos / intervalo_base) + 1
    if ritmo == "irregular":
        factores: list[float] = []
        for _ in range((cantidad_intervalos + 1) // 2):
            primer_factor = generador.uniform(0.75, 1.25)
            factores.extend((primer_factor, 2.0 - primer_factor))
    else:
        factores = [1.0] * cantidad_intervalos

    instantes_qrs: list[float] = []
    instante = 0.5
    if instante < duracion_segundos:
        instantes_qrs.append(instante)
    indice_intervalo = 0
    while instantes_qrs:
        siguiente = instantes_qrs[-1] + intervalo_base * factores[indice_intervalo]
        indice_intervalo += 1
        if siguiente <= instantes_qrs[-1]:
            raise ValueError("frecuencia cardíaca fuera de la resolución numérica")
        if siguiente >= duracion_segundos:
            break
        instantes_qrs.append(siguiente)

    muestras: list[float] = []
    for indice_muestra in range(numero_muestras):
        tiempo = indice_muestra / FRECUENCIA_MUESTREO_HZ
        valor = 0.015 * math.sin(2.0 * math.pi * 0.33 * tiempo)

        for instante_qrs in instantes_qrs:
            relativo = tiempo - instante_qrs
            if abs(relativo) > 0.42:
                continue
            if onda_p_visible:
                valor += 0.08 * math.exp(-0.5 * ((relativo + 0.18) / 0.045) ** 2)
            valor -= 0.12 * math.exp(-0.5 * ((relativo + 0.025) / 0.010) ** 2)
            valor += 1.0 * math.exp(-0.5 * (relativo / 0.012) ** 2)
            valor -= 0.25 * math.exp(-0.5 * ((relativo - 0.025) / 0.012) ** 2)
            valor += 0.30 * math.exp(-0.5 * ((relativo - 0.22) / 0.070) ** 2)

        if ruido_amplitud:
            valor += generador.uniform(-ruido_amplitud, ruido_amplitud)
        if artefacto_sintetico and 5.0 <= tiempo < 5.16:
            valor += 0.45 * math.sin(2.0 * math.pi * 18.0 * (tiempo - 5.0))

        muestras.append(round(valor, 6))

    return {
        "frecuencia_muestreo_hz": FRECUENCIA_MUESTREO_HZ,
        "muestras": muestras,
        "unidad": "mV",
    }
