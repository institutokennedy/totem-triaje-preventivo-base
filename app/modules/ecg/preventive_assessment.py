"""Fail-closed ECG rule evaluation for trusted, already-derived measurements."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.modules.ecg.schemas import (
    DatosECG,
    EvaluacionPreventivaECG,
    MetricasTecnicasSenalECG,
    ResultadoReglaClinicaECG,
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


class EvidenciaClinicaECG(BaseModel):
    """Synthetic rule-test inputs; never treated as clinical evidence."""

    procedencia: Literal["SINTETICA_PRUEBAS"] = "SINTETICA_PRUEBAS"
    calidad_senal_valida: bool | None = None
    colocacion_electrodos_correcta: bool | None = None
    inversion_electrodos_detectada: bool | None = None
    canales_ra_la_ll_disponibles: bool | None = None
    impedancia_ra_ohm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    impedancia_la_ohm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    impedancia_ll_ohm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    excepciones_colocacion_evaluadas: bool | None = None
    excepcion_colocacion_presente: bool | None = None
    velocidad_papel_mm_s: float | None = Field(default=None, allow_inf_nan=False)
    ganancia_mm_por_mv: float | None = Field(default=None, allow_inf_nan=False)
    filtro_pasa_altos_hz: float | None = Field(default=None, allow_inf_nan=False)
    filtro_pasa_bajos_hz: float | None = Field(default=None, allow_inf_nan=False)
    filtros_configurados: bool | None = None
    notch_50_hz_aplicado: bool | None = None
    artefacto_excesivo: bool | None = None
    snr_db: float | None = Field(default=None, allow_inf_nan=False)
    frecuencia_cardiaca_lpm: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    deteccion_picos_r_verificada: bool | None = None
    algoritmo_picos_r: Literal["PAN_TOMPKINS"] | None = None
    metodo_calculo_fc: Literal[
        "RR_REGULAR_300",
        "RR_REGULAR_1500",
        "QRS_6S_X10",
        "QRS_10S_X6",
    ] | None = None
    ritmo_regular_verificado: bool | None = None
    rr_cuadros_grandes: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    rr_cuadros_pequenos: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    qrs_contados: int | None = Field(default=None, gt=0)
    paciente_en_reposo: bool | None = None
    atleta_alto_rendimiento: bool | None = None
    paciente_pediatrico: bool | None = None
    intervalos_rr_ms: list[Annotated[float, Field(gt=0, allow_inf_nan=False)]] | None = None
    qrs_ms: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    limites_qrs_verificados: bool | None = None
    wolff_parkinson_white: bool | None = None
    ritmo_marcapasos: bool | None = None
    pr_ms: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    onda_p_clara: bool | None = None
    ritmo_sinusal: bool | None = None
    qt_ms: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    rr_previo_ms: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    qtc_ms: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    qtc_verificado: bool | None = None
    qtc_coherente_con_qt_rr_y_metodo: bool | None = None
    sexo_regla_qtc: Literal["H", "M"] | None = None
    metodo_qtc: Literal["BAZETT", "FRIDERICIA"] | None = None
    st_desviacion_mv: float | None = Field(default=None, allow_inf_nan=False)
    adulto: bool | None = None
    linea_isoestable: bool | None = None
    punto_j_medido: bool | None = None
    amplitud_calibrada_mv: bool | None = None
    excepcion_st_t_presente: bool | None = None


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


def _resultado(
    identificador: str,
    estado: Literal["CUMPLE", "NO_CUMPLE", "NO_EVALUABLE"],
    motivo: str,
    **valores: float,
) -> ResultadoReglaClinicaECG:
    return ResultadoReglaClinicaECG(
        identificador=identificador,
        estado=estado,
        motivo=motivo,
        valores_medidos=valores,
    )


def _regla_001(e: EvidenciaClinicaECG | None) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-001"
    if e is None or any(
        value is None
        for value in (
            e.colocacion_electrodos_correcta,
            e.inversion_electrodos_detectada,
            e.canales_ra_la_ll_disponibles,
            e.impedancia_ra_ohm,
            e.impedancia_la_ohm,
            e.impedancia_ll_ohm,
            e.excepciones_colocacion_evaluadas,
            e.excepcion_colocacion_presente,
        )
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan canales RA/LA/LL, mediciones de impedancia de contacto, "
            "verificación de posición/inversión o revisión de excepciones; "
            "LO+/LO− solo informa desconexión.",
        )
    if not e.canales_ra_la_ll_disponibles or e.excepcion_colocacion_presente:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "No se confirman todos los canales requeridos o hay una excepción "
            "documentada cuya resolución no está especificada en la ficha.",
        )
    if e.inversion_electrodos_detectada or not e.colocacion_electrodos_correcta:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "La verificación disponible indica electrodos invertidos o mal colocados; "
            "la ficha indica solicitar reposicionamiento.",
        )
    return _resultado(
        rid,
        "CUMPLE",
        "La verificación externa confirma posición correcta, sin inversión, "
        "canales RA/LA/LL y mediciones de impedancia disponibles.",
        impedancia_ra_ohm=e.impedancia_ra_ohm,
        impedancia_la_ohm=e.impedancia_la_ohm,
        impedancia_ll_ohm=e.impedancia_ll_ohm,
    )


def _regla_002(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-002"
    if datos.frecuencia_muestreo_hz < 500:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "La ficha exige frecuencia de muestreo de al menos 500 Hz; "
            f"la captura tiene {datos.frecuencia_muestreo_hz} Hz.",
            frecuencia_muestreo_hz=float(datos.frecuencia_muestreo_hz),
        )
    if e is None:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan velocidad, ganancia, configuración de filtros, rechazo de "
            "artefactos y SNR.",
        )
    required = (
        e.velocidad_papel_mm_s,
        e.ganancia_mm_por_mv,
        e.filtro_pasa_altos_hz,
        e.filtro_pasa_bajos_hz,
        e.filtros_configurados,
        e.notch_50_hz_aplicado,
        e.artefacto_excesivo,
        e.snr_db,
        e.ritmo_marcapasos,
    )
    if any(value is None for value in required):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan una o más mediciones de configuración o calidad requeridas "
            "por la ficha.",
        )
    assert e.velocidad_papel_mm_s is not None
    assert e.ganancia_mm_por_mv is not None
    assert e.filtro_pasa_altos_hz is not None
    assert e.filtro_pasa_bajos_hz is not None
    assert e.filtros_configurados is not None
    assert e.notch_50_hz_aplicado is not None
    assert e.artefacto_excesivo is not None
    assert e.snr_db is not None
    assert e.ritmo_marcapasos is not None
    filtro_en_rango = (
        0.05 <= e.filtro_pasa_altos_hz < e.filtro_pasa_bajos_hz
        and (
            e.filtro_pasa_bajos_hz == 250
            if e.ritmo_marcapasos
            else e.filtro_pasa_bajos_hz <= 150
        )
    )
    criterios = (
        e.velocidad_papel_mm_s == 25,
        e.ganancia_mm_por_mv == 10,
        filtro_en_rango,
        e.filtros_configurados,
        e.notch_50_hz_aplicado,
        not e.artefacto_excesivo,
        e.snr_db >= 15,
    )
    if not all(criterios):
        return _resultado(
            rid,
            "NO_CUMPLE",
            "La configuración o calidad incumple uno o más requisitos explícitos "
            "de la ficha (25 mm/s, 10 mm/mV, filtros 0.05–150 Hz o, para "
            "marcapasos, filtro extendido a 250 Hz, notch 50 Hz y SNR ≥15 dB).",
            snr_db=e.snr_db,
            frecuencia_muestreo_hz=float(datos.frecuencia_muestreo_hz),
        )
    return _resultado(
        rid,
        "CUMPLE",
        "La frecuencia y las mediciones recibidas cumplen los requisitos "
        "explícitos de configuración y SNR de la ficha.",
        snr_db=e.snr_db,
        frecuencia_muestreo_hz=float(datos.frecuencia_muestreo_hz),
    )


def _requiere_senal_calidad(
    rid: str, datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG | None:
    if datos.frecuencia_muestreo_hz < 500:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La señal no alcanza el requisito de calidad de muestreo de 500 Hz "
            "de la ficha RC-ECG-002.",
        )
    if e is None or e.calidad_senal_valida is not True:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "No se recibió una confirmación confiable de calidad suficiente "
            "para medir esta regla.",
        )
    return None


def _regla_003(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-003"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    assert e is not None
    if any(
        value is None
        for value in (
            e.frecuencia_cardiaca_lpm,
            e.paciente_en_reposo,
            e.atleta_alto_rendimiento,
            e.paciente_pediatrico,
            e.deteccion_picos_r_verificada,
            e.algoritmo_picos_r,
            e.metodo_calculo_fc,
            e.ritmo_regular_verificado,
        )
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan frecuencia cardíaca, confirmación de reposo o datos para "
            "resolver las excepciones de atleta/edad pediátrica o validar "
            "detección de picos R.",
        )
    if e.atleta_alto_rendimiento or e.paciente_pediatrico:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha excluye atletas de alto rendimiento y población pediátrica.",
            frecuencia_cardiaca_lpm=e.frecuencia_cardiaca_lpm,
        )
    if (
        not e.deteccion_picos_r_verificada
        or e.algoritmo_picos_r != "PAN_TOMPKINS"
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha requiere detección precisa y validada de picos R "
            "mediante Pan-Tompkins.",
            frecuencia_cardiaca_lpm=e.frecuencia_cardiaca_lpm,
        )
    if not e.paciente_en_reposo:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Los umbrales de alerta de la ficha aplican a frecuencia en reposo.",
            frecuencia_cardiaca_lpm=e.frecuencia_cardiaca_lpm,
        )
    metodos_regulares = {"RR_REGULAR_300", "RR_REGULAR_1500"}
    if e.ritmo_regular_verificado != (
        e.metodo_calculo_fc in metodos_regulares
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "El método de cálculo informado no corresponde a la clasificación "
            "verificada del ritmo.",
        )
    if e.metodo_calculo_fc == "RR_REGULAR_300":
        if e.rr_cuadros_grandes is None:
            return _resultado(
                rid,
                "NO_EVALUABLE",
                "Falta la medición R-R en cuadros grandes requerida por la ficha.",
            )
        frecuencia_calculada = 300 / e.rr_cuadros_grandes
    elif e.metodo_calculo_fc == "RR_REGULAR_1500":
        if e.rr_cuadros_pequenos is None:
            return _resultado(
                rid,
                "NO_EVALUABLE",
                "Falta la medición R-R en cuadros pequeños requerida por la ficha.",
            )
        frecuencia_calculada = 1500 / e.rr_cuadros_pequenos
    elif e.metodo_calculo_fc == "QRS_6S_X10":
        if e.qrs_contados is None or (len(datos.muestras) - 1) / datos.frecuencia_muestreo_hz < 6:
            return _resultado(
                rid,
                "NO_EVALUABLE",
                "Falta el conteo QRS o una ventana continua de 6 segundos.",
            )
        frecuencia_calculada = e.qrs_contados * 10
    else:
        if e.qrs_contados is None or (len(datos.muestras) - 1) / datos.frecuencia_muestreo_hz < 10:
            return _resultado(
                rid,
                "NO_EVALUABLE",
                "Falta el conteo QRS o una ventana continua de 10 segundos.",
            )
        frecuencia_calculada = e.qrs_contados * 6
    if e.frecuencia_cardiaca_lpm != frecuencia_calculada:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La frecuencia cardíaca informada no coincide con los datos y la "
            "fórmula especificados para el método seleccionado.",
            frecuencia_cardiaca_lpm=e.frecuencia_cardiaca_lpm,
        )
    if frecuencia_calculada < 50 or frecuencia_calculada > 120:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "Frecuencia en reposo fuera de los límites de alerta especificados "
            "(<50 o >120 LPM). La ficha no asigna color a esta alerta.",
            frecuencia_cardiaca_lpm=frecuencia_calculada,
        )
    return _resultado(
        rid,
        "NO_EVALUABLE",
        "La frecuencia no activa los umbrales de alerta explícitos, pero la ficha "
        "no define el rango normal completo ni permite inferir normalidad.",
        frecuencia_cardiaca_lpm=frecuencia_calculada,
    )


def _regla_004(datos: DatosECG, e: EvidenciaClinicaECG | None) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-004"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    duracion = (len(datos.muestras) - 1) / datos.frecuencia_muestreo_hz
    if duracion < 10:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha requiere al menos 10 segundos continuos; la captura "
            f"contiene {duracion:g} segundos.",
        )
    if e is None or not e.intervalos_rr_ms:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "No se recibieron intervalos R-R. Además, la ficha no define cortes "
            "cuantitativos para separar ritmo regular, arritmia sinusal e irregular.",
        )
    return _resultado(
        rid,
        "NO_EVALUABLE",
        "Hay intervalos R-R, pero la ficha no define cortes cuantitativos para "
        "clasificar regularidad ni las excepciones.",
    )


def _regla_005(datos: DatosECG, e: EvidenciaClinicaECG | None) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-005"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    return _resultado(
        rid,
        "NO_EVALUABLE",
        "La ficha requiere una derivación DII/V1 de alta definición, detección "
        "validada de ondas P/f y R-R irregularmente irregular; la captura actual "
        "no aporta esas mediciones y no define cómo resolver la alerta amarillo-roja "
        "ni el diagnóstico diferencial con flutter.",
    )


def _regla_006(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-006"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    if (
        e is None
        or e.qrs_ms is None
        or e.limites_qrs_verificados is None
        or e.wolff_parkinson_white is None
        or e.ritmo_marcapasos is None
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan Q_onset/S_offset verificados o la información de las "
            "excepciones WPW/marcapasos.",
        )
    if e.wolff_parkinson_white or e.ritmo_marcapasos:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha excluye síndrome de Wolff-Parkinson-White y ritmo de marcapasos.",
            qrs_ms=e.qrs_ms,
        )
    if not e.limites_qrs_verificados:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "No se validaron los límites Q_onset y S_offset.",
            qrs_ms=e.qrs_ms,
        )
    if 119 < e.qrs_ms < 120:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha especifica 100–119 ms y ≥120 ms, pero no define "
            "la fracción entre 119 y 120 ms.",
            qrs_ms=e.qrs_ms,
        )
    if e.qrs_ms < 100:
        return _resultado(
            rid,
            "CUMPLE",
            "QRS medido dentro del rango normal especificado (<100 ms).",
            qrs_ms=e.qrs_ms,
        )
    if e.qrs_ms <= 119:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "QRS en el rango de retraso de conducción especificado (100–119 ms).",
            qrs_ms=e.qrs_ms,
        )
    return _resultado(
        rid,
        "NO_CUMPLE",
        "QRS ≥120 ms; activar el flag de QRS ancho indicado en la ficha para "
        "evaluación profesional.",
        qrs_ms=e.qrs_ms,
    )


def _regla_007(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-007"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    if (
        e is None
        or e.pr_ms is None
        or e.onda_p_clara is None
        or e.ritmo_sinusal is None
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan PR medido, onda P clara o confirmación de ritmo sinusal.",
        )
    if not e.onda_p_clara or not e.ritmo_sinusal:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La ficha excluye ritmos no sinusales o sin onda P clara.",
            pr_ms=e.pr_ms,
        )
    if 120 <= e.pr_ms <= 200:
        return _resultado(
            rid,
            "CUMPLE",
            "PR dentro del rango especificado en ritmo sinusal (120–200 ms).",
            pr_ms=e.pr_ms,
        )
    return _resultado(
        rid,
        "NO_CUMPLE",
        "PR fuera del rango especificado; la ficha indica notificación preventiva.",
        pr_ms=e.pr_ms,
    )


def _regla_008(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-008"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    if (
        e is None
        or e.qt_ms is None
        or e.rr_previo_ms is None
        or e.qtc_ms is None
        or e.qtc_verificado is not True
        or e.qtc_coherente_con_qt_rr_y_metodo is not True
        or e.sexo_regla_qtc is None
        or e.frecuencia_cardiaca_lpm is None
        or e.metodo_qtc is None
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan QT, RR previo, sexo, método o una verificación de coherencia "
            "entre QT, RR y método. "
            "La ficha no permite calcular aquí QTc porque presenta una fórmula "
            "ambigua para Bazett/Fridericia.",
        )
    metodo_requerido = (
        "BAZETT"
        if 60 <= e.frecuencia_cardiaca_lpm <= 100
        else "FRIDERICIA"
    )
    if e.metodo_qtc != metodo_requerido:
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "El método informado no coincide con la selección de la ficha "
            "según frecuencia cardíaca; no se recalcula QTc.",
            qtc_ms=e.qtc_ms,
            frecuencia_cardiaca_lpm=e.frecuencia_cardiaca_lpm,
        )
    if e.qtc_ms > 500:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "QTc >500 ms; la ficha indica alerta roja de riesgo proarrítmico crítico.",
            qtc_ms=e.qtc_ms,
        )
    limite_normal = 450 if e.sexo_regla_qtc == "H" else 460
    if e.qtc_ms <= limite_normal:
        return _resultado(
            rid,
            "CUMPLE",
            "QTc dentro del límite normal explícito de la ficha para el sexo informado.",
            qtc_ms=e.qtc_ms,
        )
    return _resultado(
        rid,
        "NO_EVALUABLE",
        "QTc supera el límite normal explícito, pero el tramo prolongado "
        ">470–500 ms no tiene un corte inequívoco en la ficha.",
        qtc_ms=e.qtc_ms,
    )


def _regla_009(
    datos: DatosECG, e: EvidenciaClinicaECG | None
) -> ResultadoReglaClinicaECG:
    rid = "RC-ECG-009"
    blocked = _requiere_senal_calidad(rid, datos, e)
    if blocked:
        return blocked
    if datos.unidad != "mV":
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La amplitud está en ADC y no hay calibración a mV; no se convierte "
            "ni se interpreta como amplitud ECG.",
        )
    if (
        e is None
        or e.adulto is None
        or e.linea_isoestable is None
        or e.punto_j_medido is None
        or e.amplitud_calibrada_mv is None
        or e.excepcion_st_t_presente is None
        or e.st_desviacion_mv is None
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "Faltan confirmación de población adulta, línea isoeléctrica, punto J, "
            "calibración de amplitud, excepciones o desviación ST medida.",
        )
    if not e.adulto:
        return _resultado(rid, "NO_EVALUABLE", "La ficha aplica a mayores de 18 años.")
    if (
        not e.linea_isoestable
        or not e.punto_j_medido
        or not e.amplitud_calibrada_mv
        or e.excepcion_st_t_presente
    ):
        return _resultado(
            rid,
            "NO_EVALUABLE",
            "La línea basal/punto J no es válido, falta calibración o está "
            "presente una excepción documentada.",
        )
    if abs(e.st_desviacion_mv) >= 0.1:
        return _resultado(
            rid,
            "NO_CUMPLE",
            "Desviación ST de magnitud ≥0.1 mV; la ficha indica alerta roja inmediata. "
            "No constituye diagnóstico.",
            st_desviacion_mv=e.st_desviacion_mv,
        )
    return _resultado(
        rid,
        "NO_EVALUABLE",
        "ST está bajo el corte explícito, pero la ficha no define criterios "
        "negativos suficientes para normalidad ni umbrales de la onda T.",
        st_desviacion_mv=e.st_desviacion_mv,
    )


def _evaluar_reglas(
    datos: DatosECG, evidencia: EvidenciaClinicaECG | None
) -> list[ResultadoReglaClinicaECG]:
    return [
        _regla_001(evidencia),
        _regla_002(datos, evidencia),
        _regla_003(datos, evidencia),
        _regla_004(datos, evidencia),
        _regla_005(datos, evidencia),
        _regla_006(datos, evidencia),
        _regla_007(datos, evidencia),
        _regla_008(datos, evidencia),
        _regla_009(datos, evidencia),
    ]


def _construir_evaluacion_preventiva(
    datos: DatosECG, reglas: list[ResultadoReglaClinicaECG]
) -> EvaluacionPreventivaECG:
    estados = {regla.identificador: regla.estado for regla in reglas}
    ids_rojos = {"RC-ECG-008", "RC-ECG-009"}
    regla_calidad = estados["RC-ECG-002"]

    if any(
        regla.identificador in ids_rojos and regla.estado == "NO_CUMPLE"
        for regla in reglas
    ):
        nivel = "ROJO"
        motivo = (
            "Se activó un umbral con acción roja explícita en la ficha; requiere "
            "evaluación profesional prioritaria. No es un diagnóstico."
        )
    elif regla_calidad != "CUMPLE":
        nivel = "NO_EVALUABLE"
        motivo = (
            "La calidad/configuración ECG no cumple o no puede verificarse según "
            "la ficha; no se infiere normalidad ni se usa un resultado normal."
        )
    elif any(regla.estado == "NO_CUMPLE" for regla in reglas):
        nivel = "AMARILLO"
        motivo = (
            "Hay uno o más hallazgos que requieren revisión; otras reglas pueden "
            "seguir no evaluables. No se emite diagnóstico."
        )
    elif all(regla.estado == "CUMPLE" for regla in reglas):
        nivel = "VERDE"
        motivo = "Todas las reglas aplicables cumplen sus criterios explícitos."
    else:
        nivel = "NO_EVALUABLE"
        motivo = (
            "Una o más reglas no se pueden evaluar con las mediciones disponibles; "
            "no se infiere normalidad."
        )

    evaluadas = [
        regla for regla in reglas if regla.estado != "NO_EVALUABLE"
    ]
    valores_medidos = {
        f"{regla.identificador}.{nombre}": valor
        for regla in evaluadas
        for nombre, valor in regla.valores_medidos.items()
    }
    advertencias = list(ADVERTENCIAS_TECNICAS)
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
        nivel=nivel,
        color="GRIS" if nivel == "NO_EVALUABLE" else nivel,
        motivo=motivo,
        parametros_evaluados=[regla.identificador for regla in evaluadas],
        valores_medidos=valores_medidos,
        criterios_activados=[
            regla.identificador
            for regla in reglas
            if regla.estado == "NO_CUMPLE"
        ],
        parametros_no_evaluables=[
            f"{regla.identificador}: {regla.motivo}"
            for regla in reglas
            if regla.estado == "NO_EVALUABLE"
        ],
        calidad_senal=(
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA"
            if regla_calidad == "CUMPLE"
            else "NO EVALUADA O INSUFICIENTE"
        ),
        datos_tecnicos={
            "frecuencia_muestreo_hz": datos.frecuencia_muestreo_hz,
            "cantidad_muestras": len(datos.muestras),
            "unidad": datos.unidad,
        },
        metricas_tecnicas=_medir_datos_tecnicos(datos),
        advertencias_tecnicas=advertencias,
        reglas=reglas,
    )


def evaluar_captura_preventiva(
    datos: DatosECG, evidencia: EvidenciaClinicaECG | None = None
) -> EvaluacionPreventivaECG:
    """Evaluate a capture without accepting synthetic rule-test evidence."""
    if evidencia is not None:
        raise ValueError(
            "EvidenciaClinicaECG contiene fixtures sintéticos y solo puede "
            "utilizarse en pruebas unitarias."
        )
    return _construir_evaluacion_preventiva(
        datos,
        _evaluar_reglas(datos, None),
    )
