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
    ensayos = datos.get("ensayos")
    if isinstance(ensayos, list):
        der = sum(
            1
            for ensayo in ensayos
            if isinstance(ensayo, dict) and ensayo.get("respuesta") == "DERECHO"
        )
        izq = sum(
            1
            for ensayo in ensayos
            if isinstance(ensayo, dict) and ensayo.get("respuesta") == "IZQUIERDO"
        )
        return (
            f"{der} {'respuesta señaló' if der == 1 else 'respuestas señalaron'} el lado derecho",
            f"{izq} {'respuesta señaló' if izq == 1 else 'respuestas señalaron'} el lado izquierdo",
        )
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


def _normalizar_audiometria(datos_oido: dict | None) -> dict:
    """Arma una estructura gráfica para dibujar un audiograma."""
    if not isinstance(datos_oido, dict):
        return {"frecuencias_hz": [], "derecho": [], "izquierdo": []}

    frecuencias = datos_oido.get("frecuencias_hz") or []
    if not frecuencias and isinstance(datos_oido.get("ensayos"), list):
        frecuencias = []
        vistos = set()
        for ensayo in datos_oido["ensayos"]:
            if not isinstance(ensayo, dict):
                continue
            fq = ensayo.get("frecuencia_hz")
            if fq is None:
                continue
            if fq not in vistos:
                vistos.add(fq)
                frecuencias.append(int(fq))
        frecuencias = sorted(frecuencias)

    if not frecuencias:
        return {"frecuencias_hz": [], "derecho": [], "izquierdo": []}

    derivado = {"DERECHO": [False] * len(frecuencias), "IZQUIERDO": [False] * len(frecuencias)}
    if isinstance(datos_oido.get("resultados_oido_derecho"), list) and isinstance(datos_oido.get("resultados_oido_izquierdo"), list):
        der = datos_oido.get("resultados_oido_derecho", [])
        izq = datos_oido.get("resultados_oido_izquierdo", [])
        for idx in range(min(len(frecuencias), len(der), len(izq))):
            derivado["DERECHO"][idx] = bool(der[idx])
            derivado["IZQUIERDO"][idx] = bool(izq[idx])
    elif isinstance(datos_oido.get("ensayos"), list):
        for ensayo in datos_oido["ensayos"]:
            if not isinstance(ensayo, dict):
                continue
            fq = ensayo.get("frecuencia_hz")
            lado = ensayo.get("lado_estimulo")
            respuesta = ensayo.get("respuesta")
            if fq is None or lado not in ("DERECHO", "IZQUIERDO"):
                continue
            try:
                idx = frecuencias.index(int(fq))
            except ValueError:
                continue
            escucho = respuesta == lado and respuesta not in (None, "NO_ESCUCHE")
            derivado[lado][idx] = escucho

    def _series(lado):
        puntos = []
        for idx, fq in enumerate(frecuencias):
            puntos.append(
                {
                    "frecuencia_hz": int(fq),
                    "db": 10 + idx * 12,
                    "escucha": bool(derivado[lado][idx]),
                }
            )
        return puntos

    return {
        "frecuencias_hz": [int(f) for f in frecuencias],
        "derecho": _series("DERECHO"),
        "izquierdo": _series("IZQUIERDO"),
    }


def _audiometria_svg(audiometria: dict) -> str:
    """Genera dos gráficos de audiometría individuales con cuadrados de audio."""
    frecuencias = audiometria.get("frecuencias_hz") or []
    derecha = audiometria.get("derecho") or []
    izquierda = audiometria.get("izquierdo") or []
    if not frecuencias:
        return "<p>No hay datos de audiometría para representar.</p>"

    def _ear_svg(label, serie, color):
        ancho = 280
        alto = 220
        margen_izq = 28
        margen_der = 14
        margen_top = 16
        margen_bottom = 28
        inner_w = ancho - margen_izq - margen_der
        inner_h = alto - margen_top - margen_bottom
        y_min = 0
        y_max = 110

        def x_para(fq):
            if len(frecuencias) <= 1:
                return margen_izq + inner_w / 2
            idx = frecuencias.index(int(fq)) if int(fq) in frecuencias else 0
            return margen_izq + (idx / (len(frecuencias) - 1)) * inner_w

        def y_para(db):
            return margen_top + (1 - (db - y_min) / (y_max - y_min)) * inner_h

        puntos = []
        for punto in serie:
            fq = punto.get("frecuencia_hz")
            db = punto.get("db")
            if fq is None or db is None:
                continue
            x = x_para(fq)
            y = y_para(db)
            puntos.append((x, y, punto.get("escucha", False)))

        line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in puntos)
        circulos = []
        cruzes = []
        for x, y, escucha in puntos:
            if escucha:
                circulos.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="2" />')
            else:
                cruzes.append(f'<line x1="{x-6:.1f}" y1="{y-6:.1f}" x2="{x+6:.1f}" y2="{y+6:.1f}" stroke="{color}" stroke-width="2" />')
                cruzes.append(f'<line x1="{x+6:.1f}" y1="{y-6:.1f}" x2="{x-6:.1f}" y2="{y+6:.1f}" stroke="{color}" stroke-width="2" />')

        grid = []
        for nivel in range(0, 111, 10):
            y = y_para(nivel)
            grid.append(f'<line x1="{margen_izq}" y1="{y}" x2="{ancho-margen_der}" y2="{y}" stroke="#dfe7f5" stroke-width="1" />')
            grid.append(f'<text x="{margen_izq-8}" y="{y+3}" font-size="9" fill="#64748b" text-anchor="end">{nivel}</text>')

        x_labels = []
        for fq in frecuencias:
            x = x_para(fq)
            x_labels.append(f'<text x="{x}" y="{alto-8}" font-size="9" fill="#475569" text-anchor="middle">{fq}</text>')

        boxes = []
        for punto in serie:
            fq = punto.get("frecuencia_hz")
            escucha = bool(punto.get("escucha", False))
            if fq is None:
                continue
            class_name = "si" if escucha else "no"
            boxes.append(
                f'<div class="freq-box {class_name}"><span class="freq">{fq}Hz</span><div>{"Sí" if escucha else "No"}</div></div>'
            )

        return (
            '<div class="audiometria-ear">'
            f'<div class="audiometria-header">{label}</div>'
            f'<svg viewBox="0 0 {ancho} {alto}" width="100%" height="220" role="img" aria-label="{label}">'
            f'<line x1="{margen_izq}" y1="{margen_top}" x2="{margen_izq}" y2="{alto-margen_bottom}" stroke="#475569" stroke-width="1.2" />'
            f'<line x1="{margen_izq}" y1="{alto-margen_bottom}" x2="{ancho-margen_der}" y2="{alto-margen_bottom}" stroke="#475569" stroke-width="1.2" />'
            f'{"".join(grid)}'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{line_points}" stroke-linecap="round" stroke-linejoin="round" />'
            f'{"".join(circulos)}'
            f'{"".join(cruzes)}'
            f'{"".join(x_labels)}'
            f'<text x="18" y="{margen_top+4}" font-size="9" fill="#64748b">dB</text>'
            f'<text x="{ancho/2}" y="{alto-4}" font-size="9" fill="#64748b" text-anchor="middle">Hz</text>'
            '</svg>'
            '<div class="audiometria-legend"><span><i class="swatch si"></i>Se escucha</span><span><i class="swatch no"></i>No se escucha</span></div>'
            f'<div class="audiometria-frecuencias">{"".join(boxes)}</div>'
            '</div>'
        )

    return (
        '<div class="panel">'
        '<div class="panel-header">Audiometría</div>'
        '<div class="audiometria-grid">'
        f'{_ear_svg("Oído derecho", derecha, "#2b6cb0")}'
        f'{_ear_svg("Oído izquierdo", izquierda, "#f59e0b")}'
        '</div>'
        '</div>'
    )

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
    registros_oido = por_modulo.get("oido")
    datos_oido = registros_oido[-1].get("data") if registros_oido else {}
    der, izq = _resumen_oido(por_modulo)
    if isinstance(datos_oido, dict) and isinstance(datos_oido.get("ensayos"), list):
        mediciones.append(["Respuestas que indicaron derecha", der])
        mediciones.append(["Respuestas que indicaron izquierda", izq])
        no_escucho = sum(
            1
            for ensayo in datos_oido["ensayos"]
            if isinstance(ensayo, dict) and ensayo.get("respuesta") == "NO_ESCUCHE"
        )
        mediciones.append(["Tonos que la persona indicó no escuchar", str(no_escucho)])
    else:
        mediciones.append(["Audición oído derecho", der])
        mediciones.append(["Audición oído izquierdo", izq])
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

    audiometria = _normalizar_audiometria(registros_oido[-1].get("data") if registros_oido else {})
    datos_oido_actual = registros_oido[-1].get("data") if registros_oido else {}
    cuestionario = datos_oido_actual.get("cuestionario") if isinstance(datos_oido_actual, dict) else None

    return {
        "titulo": TITULO,
        "subtitulo": SUBTITULO,
        "paciente": datos_paciente,
        "mediciones": mediciones,
        "triaje": {"estado": estado or "PENDIENTE", "subindices": subindices},
        "analisis_ia": analisis_ia,
        "analisis_ia_estado": analisis_ia_estado,
        "alertas": alertas,
        "audiometria": audiometria,
        "cuestionario": cuestionario,
        "leyenda": LEYENDA,
    }


# ------------------------------------------------------------------ renderizado
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%);
  color: #1f2937;
  font-family: "Segoe UI", "DejaVu Sans", Verdana, Arial, sans-serif;
  font-size: 14px;
}
.pagina {
  width: min(900px, 100%);
  margin: 24px auto;
  background: #ffffff;
  border: 1px solid #dfe7f5;
  border-radius: 18px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}
.encabezado {
  background: linear-gradient(135deg, #5b2d9a 0%, #2d4ba6 100%);
  color: #ffffff;
  padding: 26px 30px 22px;
}
.eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  letter-spacing: 1.8px;
  font-weight: 700;
  text-transform: uppercase;
  opacity: 0.82;
}
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.encabezado h1 {
  margin: 0;
  font-size: clamp(24px, 3vw, 32px);
  line-height: 1.2;
  letter-spacing: 0.5px;
}
.encabezado p {
  margin: 8px 0 0;
  font-size: 12px;
  color: #e9d5ff;
  font-style: italic;
}
.badge-estado {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 160px;
  padding: 10px 16px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.18);
}
.contenido {
  padding: 24px 28px 28px;
}
.panel {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 18px;
}
.panel-header {
  margin: 0 0 12px;
  font-size: 13px;
  letter-spacing: 0.7px;
  text-transform: uppercase;
  font-weight: 800;
  color: #475569;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(180px, 1fr));
  gap: 12px 18px;
}
.metric {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
}
.metric-label {
  display: block;
  font-size: 11px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.summary-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 18px;
}
.estado-box {
  margin: 10px 0 0;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.5px;
  text-align: center;
}
.lista {
  margin: 0;
  padding-left: 18px;
  list-style: disc;
}
.lista li {
  margin: 6px 0;
  line-height: 1.45;
  color: #334155;
}
.ia-box {
  background: linear-gradient(135deg, #fff7ed 0%, #fffaf6 100%);
  border: 1px solid #fed7aa;
  border-radius: 14px;
  padding: 16px;
  margin-top: 12px;
}
.ia-box h3 {
  margin-top: 0;
  margin-bottom: 8px;
  color: #9a5b00;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.7px;
}
.leyenda {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid #dfe7f5;
  font-size: 11px;
  color: #64748b;
  text-align: center;
}
.no-print {
  text-align: center;
  padding: 0 0 22px;
}
.no-print button {
  background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%);
  color: #fff;
  border: 0;
  border-radius: 999px;
  padding: 12px 22px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(124, 58, 237, 0.25);
}
@media print {
  body { background: #fff; }
  .pagina { margin: 0; width: 100%; box-shadow: none; border: 0; border-radius: 0; }
  .no-print { display: none; }
}
@media (max-width: 700px) {
  .metric-grid { grid-template-columns: 1fr; }
  .encabezado { padding: 20px 18px; }
  .contenido { padding: 18px 16px 20px; }
  .audiometria-grid { grid-template-columns: 1fr; }
}

.audiometria-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(250px, 1fr));
  gap: 18px;
}
.audiometria-ear {
  background: #ffffff;
  border: 1px solid #dfe7f5;
  border-radius: 12px;
  padding: 12px;
}
.audiometria-header {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: #475569;
}
.audiometria-legend {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin: 8px 0 0;
  font-size: 10px;
  color: #475569;
}
.audiometria-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
.swatch.si { background: #5cc37a; }
.swatch.no { background: #ef4444; }
.audiometria-frecuencias {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.freq-box {
  width: 52px;
  text-align: center;
  border-radius: 6px;
  border: 1px solid transparent;
  padding: 4px 3px;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
}
.freq-box .freq {
  display: block;
  margin-bottom: 4px;
  color: #475569;
}
.freq-box.si {
  background: #dcfce7;
  border-color: #86efac;
  color: #166534;
}
.freq-box.no {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #991b1b;
}
"""


def _grilla(pares: list) -> str:
    celdas = "".join(f"<div>{escape(str(e))}: {escape(str(v))}</div>" for e, v in pares)
    return f'<div class="grilla">{celdas}</div>'


def _lista_html(items: list, prefijo: str) -> str:
    lis = "".join(f"<li>{prefijo}{escape(str(i))}</li>" for i in items)
    return f'<ul class="lista">{lis}</ul>'


def _formulario_oido_html(cuestionario: dict | None) -> str:
    if not isinstance(cuestionario, dict):
        return ""

    mapeo_problemas = {
        "hipoacusia": "Hipoacusia",
        "misofonia": "Misofonía",
        "reclutamiento_auditivo": "Reclutamiento auditivo",
        "fonofobia": "Fonofobia",
        "otro": "Otro",
    }
    mapeo_factores = {
        "uso_audifonos_constante": "Uso de audífonos constante",
        "hipertension": "Hipertensión",
        "antecedentes_familiares_auditivos": "Antecedentes familiares con problemas auditivos",
        "otitis_frecuentes": "Otitis frecuentes",
        "traumatismo_craneal": "Traumatismo craneal",
        "quimioterapia_ototoxicos": "Quimioterapia (fármacos ototóxicos)",
        "diabetes": "Diabetes",
        "exposicion_ruidos_fuertes": "Exposición a ruidos fuertes",
    }

    tiene_problema = bool(cuestionario.get("tiene_problema_auditivo"))
    problemas = [
        mapeo_problemas.get(str(p), str(p).replace("_", " ").capitalize())
        for p in (cuestionario.get("problemas_auditivos") or [])
    ]
    otro = (cuestionario.get("otro_problema") or "").strip()
    if otro:
        problemas.append(otro)
    factores = [
        mapeo_factores.get(str(f), str(f).replace("_", " ").capitalize())
        for f in (cuestionario.get("factores") or [])
    ]

    if not problemas and not factores and not cuestionario.get("tiene_problema_auditivo") is not False:
        return ""

    bloque_problemas = _lista_html(problemas, "• ") if problemas else "<p>No se registraron problemas auditivos.</p>"
    bloque_factores = _lista_html(factores, "• ") if factores else "<p>No se registraron factores asociados.</p>"

    respuesta = "Sí" if tiene_problema else "No"
    return (
        '<section class="panel">'
        '<div class="panel-header">Formulario</div>'
        '<div class="metric"><span class="metric-label">¿Presenta algún problema o inconveniente de audición?</span>'
        f'<span class="metric-value">{escape(respuesta)}</span></div>'
        '<div class="metric"><span class="metric-label">Problemas auditivos marcados</span>'
        f'<span class="metric-value">{escape(str(len(problemas)) if problemas else "0")}</span></div>'
        f'<div class="panel-header">Problemas auditivos</div>{bloque_problemas}'
        f'<div class="panel-header">Factores marcados</div>{bloque_factores}'
        '</section>'
    )


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
            '<div class="ia-box">'
            '<h3>Análisis orientativo asistido por IA</h3>'
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
            "</div>"
        )
    elif isinstance(reporte.get("analisis_ia_estado"), dict):
        bloque_analisis_ia = (
            '<div class="ia-box">'
            '<h3>Análisis orientativo asistido por IA</h3>'
            "<p>No disponible. El triaje permanece pendiente de revisión "
            "profesional.</p>"
            "</div>"
        )

    paciente_grid = "".join(
        '<div class="metric"><span class="metric-label">'
        f'{escape(str(etiqueta))}</span><span class="metric-value">{escape(str(valor))}</span></div>'
        for etiqueta, valor in reporte["paciente"]
    )
    mediciones_grid = "".join(
        '<div class="metric"><span class="metric-label">'
        f'{escape(str(etiqueta))}</span><span class="metric-value">{escape(str(valor))}</span></div>'
        for etiqueta, valor in reporte["mediciones"]
    )

    bloque_alertas = _lista_html(reporte["alertas"], "• ")
    bloque_audiometria = _audiometria_svg(reporte.get("audiometria", {}))
    bloque_formulario = _formulario_oido_html(reporte.get("cuestionario"))

    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(reporte['titulo'])}</title><style>{CSS}</style></head><body>"
        '<div class="pagina">'
        '<div class="encabezado">'
        '<div class="header-row">'
        '<div>'
        '<p class="eyebrow">Tótem de triaje preventivo</p>'
        f'<h1>{escape(reporte["titulo"])}</h1>'
        f'<p>{escape(reporte["subtitulo"])}</p>'
        '</div>'
        f'<div class="badge-estado" style="background:{fondo};color:{texto}">ESTADO: {escape(estado)}</div>'
        '</div>'
        '</div>'
        '<div class="contenido">'
        '<section class="panel">'
        '<div class="panel-header">Datos del paciente</div>'
        f'<div class="metric-grid">{paciente_grid}</div>'
        '</section>'
        '<section class="panel">'
        '<div class="panel-header">Mediciones registradas</div>'
        f'<div class="metric-grid">{mediciones_grid}</div>'
        '</section>'
        f'{bloque_audiometria}'
        '<section class="summary-card">'
        '<div class="panel-header">Resultado preventivo general</div>'
        f'<div class="estado-box" style="background:{fondo};color:{texto}">ESTADO DEL TRIAJE: {escape(estado)}</div>'
        f'{bloque_sub if bloque_sub else "<p>No hay subíndices reportados.</p>"}'
        f'{bloque_analisis_ia}'
        '</section>'
        '<section class="panel">'
        '<div class="panel-header">Observaciones / alertas</div>'
        f'{bloque_alertas}'
        '</section>'
        f'{bloque_formulario}'
        f'<p class="leyenda">{escape(reporte["leyenda"])}</p>'
        '</div></div>'
        '<div class="no-print"><button type="button" onclick="window.print()">Imprimir / Guardar como PDF</button></div>'
        '</body></html>'
    )