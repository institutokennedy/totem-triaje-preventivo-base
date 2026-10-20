"""Construcción y renderizado del Reporte Preventivo de Triaje (informe final).

- construir_reporte(): arma un diccionario serializable (se guarda en Informe.contenido_json).
- render_html(): genera el HTML del informe, con el estilo del reporte impreso.

Las claves que se buscan en los resultados de cada módulo están en CAMPOS_MEDICIONES
y en _datos_triaje(); si otro grupo usa nombres distintos, basta con editarlas ahí.
"""
from datetime import date, datetime
from html import escape

LEYENDA = "Informe preventivo. No constituye un diagnóstico médico."
TITULO = "REPORTE PREVENTIVO DE TRIAJE"
SUBTITULO = "Tótem de Triaje Inteligente - Sistema de Monitoreo Escolar"
NO_REGISTRADO = "No registrado"

# (etiqueta, claves candidatas en data_json, unidad). Orden = orden de lectura (2 columnas).
CAMPOS_MEDICIONES = [
    ("Frecuencia Cardíaca", ("frecuencia_cardiaca", "fc", "bpm", "lpm"), "lpm"),
    ("Presión Arterial", None, ""),  # caso especial: sistólica/diastólica
    ("Saturación de Oxígeno (SpO2)", ("spo2", "saturacion_oxigeno", "saturacion"), "%"),
    ("Temperatura Corporal", ("temperatura_corporal", "temperatura", "temp"), "°C"),
    ("Peso", ("peso_kg", "peso"), "kg"),
    ("Altura", ("altura_cm", "altura", "talla_cm", "talla"), "cm"),
    ("Calidad de ECG", ("calidad_ecg", "ecg_calidad"), ""),
]

NOMBRES_SUBINDICES = {
    "cardiovascular": "Cardiovascular",
    "termico": "Térmico",
    "antropometrico": "Antropométrico",
}

# estado -> (fondo, texto)
COLORES_ESTADO = {
    "ROJO": ("#fee2e2", "#991b1b"),
    "AMARILLO": ("#fef9c3", "#854d0e"),
    "VERDE": ("#dcfce7", "#166534"),
}
COLOR_PENDIENTE = ("#e2e8f0", "#475569")


# ------------------------------------------------------------------ utilidades
def _buscar(por_modulo: dict, claves) -> object:
    """Devuelve el primer valor encontrado (registro más reciente primero)."""
    for registros in por_modulo.values():
        for reg in reversed(registros):
            datos = reg.get("data")
            if not isinstance(datos, dict):
                continue
            niveles = [datos] + [v for v in datos.values() if isinstance(v, dict)]
            for nivel in niveles:
                for clave in claves:
                    if nivel.get(clave) is not None:
                        return nivel[clave]
    return None


def _con_unidad(valor, unidad: str) -> str:
    if valor is None:
        return NO_REGISTRADO
    return f"{valor} {unidad}".strip()


def _presion(por_modulo: dict) -> str:
    texto = _buscar(por_modulo, ("presion_arterial", "presion"))
    if texto is not None:
        return str(texto) if "mmHg" in str(texto) else f"{texto} mmHg"
    sis = _buscar(por_modulo, ("presion_sistolica", "sistolica"))
    dia = _buscar(por_modulo, ("presion_diastolica", "diastolica"))
    if sis is not None and dia is not None:
        return f"{sis}/{dia} mmHg"
    return NO_REGISTRADO


def _edad(paciente) -> str:
    nacimiento = getattr(paciente, "fecha_nacimiento", None)
    if isinstance(nacimiento, str):
        try:
            nacimiento = date.fromisoformat(nacimiento)
        except ValueError:
            nacimiento = None
    if not nacimiento:
        return NO_REGISTRADO
    hoy = date.today()
    anios = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
    return f"{anios} años"


def _resumen_oido(por_modulo: dict):
    """Devuelve (texto_derecho, texto_izquierdo) a partir del último registro de oído."""
    registros = por_modulo.get("oido")
    datos = registros[-1].get("data") if registros else None
    if not isinstance(datos, dict):
        return NO_REGISTRADO, NO_REGISTRADO
    n = len(datos.get("frecuencias_hz", []))
    der = sum(1 for x in datos.get("resultados_oido_derecho", []) if x is True)
    izq = sum(1 for x in datos.get("resultados_oido_izquierdo", []) if x is True)
    return (
        f"{der} de {n} frecuencias con respuesta",
        f"{izq} de {n} frecuencias con respuesta",
    )


def _datos_triaje(por_modulo: dict) -> dict:
    """Lee el resultado del análisis de triaje si otro módulo ya lo guardó."""
    for nombre in ("triaje", "triage"):
        registros = por_modulo.get(nombre)
        if registros and isinstance(registros[-1].get("data"), dict):
            return registros[-1]["data"]
    return {}


def _lista(valor) -> list:
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return [str(v) for v in valor]


# ------------------------------------------------------------------ construcción
def construir_reporte(
    paciente,
    por_modulo: dict,
    pendientes: list,
    ahora: datetime | None = None,
    analisis_ia: dict | None = None,
    analisis_ia_estado: dict | None = None,
) -> dict:
    ahora = ahora or datetime.now()

    nombre = " ".join(
        p for p in (getattr(paciente, "nombre", ""), getattr(paciente, "apellido", "")) if p
    ).strip()
    correo = next(
        (getattr(paciente, c) for c in ("correo", "email", "correo_electronico") if getattr(paciente, c, None)),
        None,
    )
    datos_paciente = [
        ["Nombre Completo", nombre or NO_REGISTRADO],
        ["Fecha/Hora", ahora.strftime("%d/%m/%Y %H:%M")],
        ["Edad", _edad(paciente)],
        ["Correo", correo or NO_REGISTRADO],
    ]

    mediciones = []
    for etiqueta, claves, unidad in CAMPOS_MEDICIONES:
        if claves is None:
            mediciones.append([etiqueta, _presion(por_modulo)])
        else:
            mediciones.append([etiqueta, _con_unidad(_buscar(por_modulo, claves), unidad)])
    der, izq = _resumen_oido(por_modulo)
    mediciones.append(["Audición oído derecho", der])
    mediciones.append(["Audición oído izquierdo", izq])
    registros_oido = por_modulo.get("oido")
    datos_oido = registros_oido[-1].get("data") if registros_oido else {}
    nivel_senal = (
        datos_oido.get("nivel_senal", "NORMAL")
        if isinstance(datos_oido, dict)
        else "NORMAL"
    )
    mediciones.append(
        [
            "Nivel de señal auditiva",
            "Reducido por autoinforme"
            if nivel_senal == "REDUCIDO_POR_AUTOINFORME"
            else "Normal (no calibrado)",
        ]
    )

    triaje = _datos_triaje(por_modulo)
    estado = str(triaje.get("estado") or triaje.get("estado_triaje") or "").strip().upper()
    subindices = []
    sub = triaje.get("subindices")
    if isinstance(sub, dict):
        for clave, valor in sub.items():
            nombre_sub = NOMBRES_SUBINDICES.get(str(clave).lower(), str(clave).replace("_", " ").capitalize())
            subindices.append([nombre_sub, str(valor).capitalize()])

    alertas = _lista(triaje.get("alertas") or triaje.get("observaciones"))
    if pendientes:
        alertas.append("Módulos pendientes de evaluación: " + ", ".join(pendientes) + ".")
    if not alertas:
        alertas.append("Sin alertas registradas.")

    return {
        "titulo": TITULO,
        "subtitulo": SUBTITULO,
        "paciente": datos_paciente,
        "mediciones": mediciones,
        "triaje": {"estado": estado or "PENDIENTE", "subindices": subindices},
        "analisis_ia": analisis_ia,
        "analisis_ia_estado": analisis_ia_estado,
        "alertas": alertas,
        "leyenda": LEYENDA,
    }


# ------------------------------------------------------------------ renderizado
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; background: #e5e7eb; color: #334155; font-size: 14px;
       font-family: "DejaVu Sans", Verdana, Arial, sans-serif; }
.pagina { width: 100%; max-width: 800px; min-height: 1000px; margin: 0 auto; background: #fff; }
.encabezado { background: #1e40af; color: #fff; text-align: center; padding: 2.2rem 1rem 1.8rem; }
.encabezado h1 { margin: 0; font-size: 26px; letter-spacing: .5px; }
.encabezado p { margin: .7rem 0 0; font-size: 12px; font-style: italic; color: #dbeafe; }
.contenido { padding: .6rem 2.4rem 2rem; }
h2 { background: #f1f5f9; color: #1e293b; font-size: 15px; text-transform: uppercase;
     padding: .55rem .9rem; margin: 1.5rem 0 .8rem; }
.grilla { display: flex; flex-wrap: wrap; padding: 0 .3rem; }
.grilla div { width: 50%; padding: .22rem 1rem .22rem 0; }
.estado { padding: .9rem 1.1rem; font-size: 20px; font-weight: 700; margin-bottom: .9rem; }
.lista { margin: 0; padding: 0 .3rem; list-style: none; }
.lista li { padding: .18rem 0; }
.leyenda { margin-top: 2rem; padding-top: .8rem; border-top: 1px solid #cbd5e1;
           font-size: 11px; color: #64748b; }
.no-print { text-align: center; padding: 1rem; }
.no-print button { background: #1e40af; color: #fff; border: 0; border-radius: 6px;
                   padding: .6rem 1.2rem; font-size: 14px; cursor: pointer; }
@media print { body { background: #fff; } .pagina { max-width: none; } .no-print { display: none; } }
"""


def _grilla(pares: list) -> str:
    celdas = "".join(f"<div>{escape(str(e))}: {escape(str(v))}</div>" for e, v in pares)
    return f'<div class="grilla">{celdas}</div>'


def _lista_html(items: list, prefijo: str) -> str:
    lis = "".join(f"<li>{prefijo}{escape(str(i))}</li>" for i in items)
    return f'<ul class="lista">{lis}</ul>'


def render_html(reporte: dict) -> str:
    estado = reporte["triaje"]["estado"]
    fondo, texto = COLORES_ESTADO.get(estado, COLOR_PENDIENTE)

    subindices = [f"Subíndice {n}: {v}" for n, v in reporte["triaje"]["subindices"]]
    bloque_sub = _lista_html(subindices, "• ") if subindices else ""
    analisis_ia = reporte.get("analisis_ia")
    bloque_analisis_ia = ""
    if isinstance(analisis_ia, dict):
        motivos = _lista_html(analisis_ia.get("motivos", []), "• ")
        alertas_ia = _lista_html(analisis_ia.get("alertas", []), "• ")
        subindices_ia = _lista_html(
            [
                f"{nombre}: {estado}"
                for nombre, estado in analisis_ia.get("subindices", {}).items()
            ],
            "• ",
        )
        bloque_analisis_ia = (
            "<h2>Análisis orientativo asistido por IA</h2>"
            '<p><strong>Requiere revisión profesional; no constituye diagnóstico '
            "ni clasificación clínica validada.</strong></p>"
            f'<p><strong>Nivel sugerido (no validado):</strong> '
            f'{escape(str(analisis_ia.get("estado", "PENDIENTE")))}</p>'
            f'<p>{escape(str(analisis_ia.get("resumen", "")))}</p>'
            f"<h3>Subíndices sugeridos (no validados)</h3>{subindices_ia}"
            f"<h3>Motivos</h3>{motivos}"
            f"<h3>Alertas</h3>{alertas_ia}"
            f'<p><strong>Recomendación orientativa:</strong> '
            f'{escape(str(analisis_ia.get("recomendacion", "")))}</p>'
        )
    elif isinstance(reporte.get("analisis_ia_estado"), dict):
        bloque_analisis_ia = (
            "<h2>Análisis orientativo asistido por IA</h2>"
            "<p>No disponible. El triaje permanece pendiente de revisión "
            "profesional.</p>"
        )

    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(reporte['titulo'])}</title><style>{CSS}</style></head><body>"
        '<div class="pagina">'
        f'<div class="encabezado"><h1>{escape(reporte["titulo"])}</h1>'
        f'<p>{escape(reporte["subtitulo"])}</p></div>'
        '<div class="contenido">'
        "<h2>Datos del paciente</h2>" + _grilla(reporte["paciente"]) +
        "<h2>Mediciones registradas (sensores)</h2>" + _grilla(reporte["mediciones"]) +
        "<h2>Resultado preventivo general</h2>"
        f'<div class="estado" style="background:{fondo};color:{texto}">'
        f"ESTADO DEL TRIAJE: {escape(estado)}</div>" + bloque_sub +
        bloque_analisis_ia +
        "<h2>Observaciones / Alertas</h2>" + _lista_html(reporte["alertas"], "- ") +
        f'<p class="leyenda">{escape(reporte["leyenda"])}</p>'
        "</div></div>"
        '<div class="no-print"><button type="button" onclick="window.print()">'
        "Imprimir / Guardar como PDF</button></div>"
        "</body></html>"
    )