"""Preventive ECG assessment that fails closed while clinical criteria are unsupported."""

from app.modules.ecg.schemas import (
    DatosECG,
    EvaluacionPreventivaECG,
    MetricasTecnicasSenalECG,
)


ADVERTENCIAS_TECNICAS = [
    "Ruido eléctrico e interferencias pueden alterar la señal.",
    "El movimiento puede introducir artefactos.",
    "El contacto deficiente o la desconexión de electrodos pueden invalidar la captura.",
    "Las variaciones de la línea de base pueden distorsionar las mediciones.",
    "La frecuencia de muestreo y la resolución del ADC limitan la precisión.",
    "La detección incorrecta de ondas P, QRS o T puede producir mediciones erróneas.",
    "La estimación de intervalos puede contener errores.",
    "Un problema técnico de adquisición no equivale a una alerta clínica.",
]


def _medir_datos_tecnicos(datos: DatosECG) -> MetricasTecnicasSenalECG:
    muestras = datos.muestras
    minimo = min(muestras)
    maximo = max(muestras)
    return MetricasTecnicasSenalECG(
        duracion_entre_muestras_segundos=(
            (len(muestras) - 1) / datos.frecuencia_muestreo_hz
        ),
        amplitud_minima=minimo,
        amplitud_maxima=maximo,
        amplitud_rango=maximo - minimo,
        muestras_distintas=len(set(muestras)),
        muestras_adc_en_riel_inferior=(
            sum(muestra == 0 for muestra in muestras)
            if datos.unidad == "ADC"
            else None
        ),
        muestras_adc_en_riel_superior=(
            sum(muestra == 4095 for muestra in muestras)
            if datos.unidad == "ADC"
            else None
        ),
    )


def _parametros_no_evaluables(datos: DatosECG) -> list[str]:
    requisitos_calidad = (
        "la frecuencia es menor que 500 Hz; "
        if datos.frecuencia_muestreo_hz < 500
        else ""
    )
    requisitos_calidad += (
        "las muestras ADC no tienen calibración a mV; "
        if datos.unidad == "ADC"
        else "no se recibe metadato de calibración en mV; "
    )
    requisitos_calidad += (
        "no se aplican los filtros especificados ni se calcula SNR, por lo "
        "que no se puede aplicar el umbral de rechazo SNR <15 dB."
    )
    return [
        (
            "RC-ECG-001 · Colocación/inversión de electrodos: faltan los "
            "canales RA, LA y LL y la impedancia; LO+/LO− solo indica "
            "desconexión y no se conserva junto a la captura."
        ),
        f"RC-ECG-002 · Calidad de señal: {requisitos_calidad}",
        (
            "RC-ECG-003 · Frecuencia cardíaca: no hay detección validada de "
            "picos R ni estado de reposo; la estimación experimental del "
            "firmware no forma parte del resultado persistido."
        ),
        (
            "RC-ECG-004 · Regularidad: no se detectan intervalos R-R; la "
            "ficha tampoco fija umbrales cuantitativos de variabilidad ni "
            "cómo resolver las excepciones indicadas."
        ),
        (
            "RC-ECG-005 · Fibrilación auricular: faltan derivaciones DII/V1 "
            "de alta definición sin artefactos y detección de ondas P, ondas "
            "f y picos R; la ficha no determina un nivel único entre amarillo "
            "y rojo."
        ),
        (
            "RC-ECG-006 · Duración QRS: no se detectan Q_onset ni S_offset; "
            "tampoco se determina el nivel preventivo del retraso o del flag "
            "QRS ancho."
        ),
        (
            "RC-ECG-007 · Intervalo PR: no se detectan P_onset ni QRS_onset "
            "y no se confirma ritmo sinusal para aplicar el rango."
        ),
        (
            "RC-ECG-008 · QT/QTc: faltan QT, RR previo y sexo. La ficha "
            "presenta un umbral prolongado ambiguo (>470–500 ms) y no "
            "especifica fórmulas diferenciadas e inequívocas para Bazett y "
            "Fridericia."
        ),
        (
            "RC-ECG-009 · ST/onda T: faltan punto J, línea isoeléctrica "
            "estable y amplitud calibrada en mV; una sola derivación no "
            "permite asumir los criterios generales documentados."
        ),
    ]


def evaluar_captura_preventiva(datos: DatosECG) -> EvaluacionPreventivaECG:
    """Keep the assessment gray until the capture supports documented measurements."""
    advertencias = list(ADVERTENCIAS_TECNICAS)
    if datos.frecuencia_muestreo_hz < 500:
        motivo_frecuencia = (
            "No cumple el requisito documentado de al menos 500 Hz. "
        )
    else:
        motivo_frecuencia = (
            "Aunque alcanza la frecuencia mínima documentada, faltan los "
            "demás requisitos técnicos y mediciones. "
        )
    descripcion_senal = (
        "cuentas ADC crudas"
        if datos.unidad == "ADC"
        else "muestras en mV sin metadatos de calibración"
    )
    if datos.frecuencia_muestreo_hz < 500:
        advertencias.append(
            "La ficha de calidad exige una frecuencia de muestreo de al menos "
            "500 Hz; esta captura no cumple ese requisito."
        )
    if datos.unidad == "ADC":
        advertencias.append(
            "Las cuentas ADC no se convierten a mV y no hay calibración de amplitud."
        )

    return EvaluacionPreventivaECG(
        nivel="NO_EVALUABLE",
        color="GRIS",
        motivo=(
            f"NO EVALUABLE: la captura conserva {descripcion_senal} de una "
            f"derivación a {datos.frecuencia_muestreo_hz} Hz. {motivo_frecuencia}"
            "No aporta calidad de señal ni detección de ondas e intervalos. "
            "Ninguna regla clínica puede aplicarse con fiabilidad; no se infiere "
            "normalidad ni se emite un diagnóstico."
        ),
        parametros_evaluados=[],
        valores_medidos={},
        criterios_activados=[],
        parametros_no_evaluables=_parametros_no_evaluables(datos),
        calidad_senal="NO EVALUADA",
        datos_tecnicos={
            "frecuencia_muestreo_hz": datos.frecuencia_muestreo_hz,
            "cantidad_muestras": len(datos.muestras),
            "unidad": datos.unidad,
        },
        metricas_tecnicas=_medir_datos_tecnicos(datos),
        advertencias_tecnicas=advertencias,
    )
