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


def _resultados_reales_oido(datos_oido: dict | None, origen: str | None) -> dict | None:
    """Normaliza únicamente respuestas que realmente fueron guardadas por la prueba."""
    if not isinstance(datos_oido, dict):
        return None

    ensayos = datos_oido.get("ensayos")
    frecuencias_legacy = datos_oido.get("frecuencias_hz") or []
    ensayos_validos = []
    if isinstance(ensayos, list):
        ensayos_validos = [
            ensayo
            for ensayo in ensayos
            if isinstance(ensayo, dict)
            and isinstance(ensayo.get("frecuencia_hz"), int)
            and not isinstance(ensayo.get("frecuencia_hz"), bool)
            and ensayo["frecuencia_hz"] > 0
            and ensayo.get("lado_estimulo") in ("DERECHO", "IZQUIERDO")
            and ensayo.get("respuesta") in ("DERECHO", "IZQUIERDO", "NO_ESCUCHE")
        ]

    if ensayos_validos:
        frecuencias = sorted({ensayo["frecuencia_hz"] for ensayo in ensayos_validos})
        percibidos = {
            lado: {frecuencia: None for frecuencia in frecuencias}
            for lado in ("DERECHO", "IZQUIERDO")
        }
        for ensayo in ensayos_validos:
            percibidos[ensayo["lado_estimulo"]][ensayo["frecuencia_hz"]] = (
                ensayo["respuesta"] != "NO_ESCUCHE"
            )
        resultados = {
            "derecho": [percibidos["DERECHO"][frecuencia] for frecuencia in frecuencias],
            "izquierdo": [percibidos["IZQUIERDO"][frecuencia] for frecuencia in frecuencias],
        }
    else:
        if not isinstance(frecuencias_legacy, list):
            return None
        frecuencias_origen = [
            frecuencia
            for frecuencia in frecuencias_legacy
            if isinstance(frecuencia, int)
            and not isinstance(frecuencia, bool)
            and frecuencia > 0
        ]
        frecuencias = sorted(set(frecuencias_origen))
        if not frecuencias:
            return None
        resultados = {}
        for lado, campo in (
            ("derecho", "resultados_oido_derecho"),
            ("izquierdo", "resultados_oido_izquierdo"),
        ):
            valores = datos_oido.get(campo)
            por_frecuencia = {}
            if isinstance(valores, list):
                por_frecuencia = {
                    frecuencia: valor
                    for frecuencia, valor in zip(frecuencias_legacy, valores)
                    if isinstance(frecuencia, int)
                    and not isinstance(frecuencia, bool)
                    and frecuencia in frecuencias
                    and isinstance(valor, bool)
                }
            resultados[lado] = [
                por_frecuencia.get(frecuencia) for frecuencia in frecuencias
            ]

    return {
        "frecuencias_hz": frecuencias,
        "resultados_oido_derecho": resultados["derecho"],
        "resultados_oido_izquierdo": resultados["izquierdo"],
        "origen": origen,
    }


def _normalizar_audiometria(datos_oido: dict | None) -> dict:
    """Prepara respuestas por lado y frecuencia sin inferir umbrales en dB HL."""
    if not isinstance(datos_oido, dict):
        return {"frecuencias_hz": [], "derecho": [], "izquierdo": [], "modo": "localizacion"}

    ensayos = datos_oido.get("ensayos")
    frecuencias = []
    frecuencias_legacy = datos_oido.get("frecuencias_hz") or []
    if isinstance(ensayos, list):
        for ensayo in ensayos:
            if not isinstance(ensayo, dict):
                continue
            frecuencia = ensayo.get("frecuencia_hz")
            if isinstance(frecuencia, int) and not isinstance(frecuencia, bool) and frecuencia > 0:
                frecuencias.append(frecuencia)
    if not frecuencias:
        for frecuencia in frecuencias_legacy:
            if isinstance(frecuencia, int) and not isinstance(frecuencia, bool) and frecuencia > 0:
                frecuencias.append(frecuencia)
    frecuencias = sorted(set(frecuencias))

    modo = "localizacion" if isinstance(ensayos, list) else "deteccion"
    resultados = {
        lado: {frecuencia: None for frecuencia in frecuencias}
        for lado in ("DERECHO", "IZQUIERDO")
    }
    if modo == "localizacion":
        for ensayo in datos_oido["ensayos"]:
            if not isinstance(ensayo, dict):
                continue
            frecuencia = ensayo.get("frecuencia_hz")
            lado_estimulo = ensayo.get("lado_estimulo")
            respuesta = ensayo.get("respuesta")
            if frecuencia not in frecuencias or lado_estimulo not in resultados:
                continue
            if respuesta == lado_estimulo:
                resultado = "CORRECTA"
            elif respuesta in ("DERECHO", "IZQUIERDO"):
                resultado = "LADO_OPUESTO"
            elif respuesta == "NO_ESCUCHE":
                resultado = "NO_ESCUCHE"
            else:
                continue
            resultados[lado_estimulo][frecuencia] = resultado
    else:
        derecha = datos_oido.get("resultados_oido_derecho")
        izquierda = datos_oido.get("resultados_oido_izquierdo")
        for lado, valores in (("DERECHO", derecha), ("IZQUIERDO", izquierda)):
            if not isinstance(valores, list):
                continue
            for frecuencia, valor in zip(frecuencias_legacy, valores):
                if (
                    isinstance(frecuencia, int)
                    and not isinstance(frecuencia, bool)
                    and frecuencia in resultados[lado]
                    and isinstance(valor, bool)
                ):
                    resultados[lado][frecuencia] = (
                        "PERCIBIDO" if valor else "NO_PERCIBIDO"
                    )

    def _series(lado):
        return [
            {"frecuencia_hz": frecuencia, "respuesta": resultados[lado][frecuencia]}
            for frecuencia in frecuencias
        ]

    return {
        "frecuencias_hz": frecuencias,
        "derecho": _series("DERECHO"),
        "izquierdo": _series("IZQUIERDO"),
        "modo": modo,
    }


def _audiometria_svg(audiometria: dict) -> str:
    """Dibuja resultados auditivos por frecuencia, sin simular valores dB HL."""
    frecuencias = audiometria.get("frecuencias_hz") or []
    derecha = audiometria.get("derecho") or []
    izquierda = audiometria.get("izquierdo") or []
    if not frecuencias:
        return "<p>No hay datos de audiometría para representar.</p>"

    modo = audiometria.get("modo", "localizacion")
    categorias = (
        [
            ("CORRECTA", "Lado correcto"),
            ("LADO_OPUESTO", "Lado opuesto"),
            ("NO_ESCUCHE", "No escuchó"),
        ]
        if modo == "localizacion"
        else [("PERCIBIDO", "Percibido"), ("NO_PERCIBIDO", "No percibido")]
    )
    pie = (
        "La posición vertical muestra la respuesta de localización, no un umbral."
        if modo == "localizacion"
        else "Resultado de detección registrado en el formato anterior."
    )

    def _ear_svg(label, serie, color, marcador):
        ancho = 640
        alto = 340
        margen_izq = 142
        margen_der = 22
        margen_top = 42
        margen_bottom = 66
        inner_w = ancho - margen_izq - margen_der
        inner_h = alto - margen_top - margen_bottom
        frecuencia_posicion = {frecuencia: indice for indice, frecuencia in enumerate(frecuencias)}
        categoria_posicion = {
            codigo: margen_top + (indice + 0.5) * inner_h / len(categorias)
            for indice, (codigo, _) in enumerate(categorias)
        }

        def x_para(fq):
            if len(frecuencias) <= 1:
                return margen_izq + inner_w / 2
            idx = frecuencia_posicion.get(int(fq), 0)
            return margen_izq + (idx / (len(frecuencias) - 1)) * inner_w

        bandas = []
        etiquetas_y = []
        for indice, (codigo, etiqueta) in enumerate(categorias):
            y0 = margen_top + indice * inner_h / len(categorias)
            y1 = margen_top + (indice + 1) * inner_h / len(categorias)
            fondo = "#f8fafc" if indice % 2 == 0 else "#ffffff"
            bandas.append(
                f'<rect x="{margen_izq}" y="{y0:.1f}" width="{inner_w:.1f}" height="{y1-y0:.1f}" fill="{fondo}" />'
            )
            etiquetas_y.append(
                f'<text x="{margen_izq-12}" y="{(y0+y1)/2+4:.1f}" '
                f'font-size="13" fill="#475569" text-anchor="end">{etiqueta}</text>'
            )
            bandas.append(
                f'<line x1="{margen_izq}" y1="{y1:.1f}" x2="{ancho-margen_der}" y2="{y1:.1f}" '
                f'stroke="#dbe4ee" stroke-width="1" />'
            )
        rejilla_x = []
        etiquetas_x = []
        for frecuencia in frecuencias:
            x = x_para(frecuencia)
            rejilla_x.append(
                f'<line x1="{x:.1f}" y1="{margen_top}" x2="{x:.1f}" y2="{alto-margen_bottom}" '
                'stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3 4" />'
            )
            etiquetas_x.append(
                f'<text x="{x:.1f}" y="{alto-margen_bottom+22}" font-size="12" '
                f'fill="#334155" text-anchor="middle">{frecuencia}</text>'
            )
        puntos = []
        for punto in serie:
            frecuencia = punto.get("frecuencia_hz")
            respuesta = punto.get("respuesta")
            if frecuencia not in frecuencia_posicion or respuesta not in categoria_posicion:
                continue
            puntos.append((x_para(frecuencia), categoria_posicion[respuesta]))

        trazado = ""
        if len(puntos) > 1:
            coords = " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)
            trazado = (
                f'<polyline points="{coords}" fill="none" stroke="{color}" '
                'stroke-width="3" stroke-linecap="round" stroke-linejoin="round" opacity=".8" />'
            )
        marcadores = []
        for x, y in puntos:
            if marcador == "circulo":
                marcadores.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" stroke="#ffffff" stroke-width="2" />'
                )
            else:
                marcadores.append(
                    f'<path d="M{x-7:.1f},{y-7:.1f} L{x+7:.1f},{y+7:.1f} '
                    f'M{x+7:.1f},{y-7:.1f} L{x-7:.1f},{y+7:.1f}" '
                    f'fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" />'
                )

        clase_lado = "derecho" if marcador == "circulo" else "izquierdo"
        etiquetas_respuesta = {
            "CORRECTA": ("Lado correcto", "correcta"),
            "LADO_OPUESTO": ("Lado opuesto", "lado-opuesto"),
            "NO_ESCUCHE": ("No escuchó", "no-escuche"),
            "PERCIBIDO": ("Percibido", "percibido"),
            "NO_PERCIBIDO": ("No percibido", "no-percibido"),
        }
        tarjetas_frecuencia = []
        for punto in serie:
            etiqueta, clase = etiquetas_respuesta.get(
                punto.get("respuesta"), ("Sin respuesta", "")
            )
            tarjetas_frecuencia.append(
                f'<div class="freq-box {clase}">'
                f'<strong>{escape(str(punto.get("frecuencia_hz")))} Hz</strong>'
                f'{escape(etiqueta)}</div>'
            )
        detalle_frecuencias = "".join(tarjetas_frecuencia)
        resultados_audicion = []
        for punto in serie:
            respuesta = punto.get("respuesta")
            if respuesta in ("CORRECTA", "LADO_OPUESTO", "PERCIBIDO"):
                etiqueta_audicion, clase_audicion = "Sí", "si"
            elif respuesta in ("NO_ESCUCHE", "NO_PERCIBIDO"):
                etiqueta_audicion, clase_audicion = "No", "no"
            else:
                etiqueta_audicion, clase_audicion = "Sin resp.", ""
            resultados_audicion.append(
                f'<div class="audicion-frecuencia {clase_audicion}">'
                f'<strong>{escape(str(punto.get("frecuencia_hz")))} Hz</strong>'
                f'{etiqueta_audicion}</div>'
            )
        resumen_audicion = "".join(resultados_audicion)
        return (
            '<section class="audiometria-ear">'
            f'<div class="audiometria-header {clase_lado}">{label}</div>'
            f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="Respuesta del {label.lower()} por frecuencia">'
            f'<title>Respuesta del {label.lower()} por frecuencia</title>'
            f'<desc>{pie} No representa umbrales en dB HL.</desc>'
            f'{"".join(bandas)}{"".join(rejilla_x)}{"".join(etiquetas_y)}'
            f'{trazado}{"".join(marcadores)}{"".join(etiquetas_x)}'
            f'<text x="{margen_izq+inner_w/2:.1f}" y="{alto-14}" font-size="13" '
            'fill="#334155" text-anchor="middle">Frecuencia (Hz)</text>'
            f'<text x="18" y="{margen_top+inner_h/2:.1f}" font-size="12" fill="#64748b" '
            'text-anchor="middle" transform="rotate(-90 18 '
            f'{margen_top+inner_h/2:.1f})">Respuesta</text>'
            '</svg>'
            '<div class="audiometria-detalle">'
            '<h3>Detalle por frecuencia</h3>'
            f'<div class="audiometria-frecuencias">{detalle_frecuencias}</div>'
            '</div>'
            '<div class="audicion-resumen" aria-label="Resumen de tonos escuchados">'
            '<div class="audicion-leyenda">'
            '<span><i class="audicion-indicador"></i>Se escucha</span>'
            '<span><i class="audicion-indicador no"></i>No se escucha</span>'
            '</div>'
            f'<div class="audicion-resultados">{resumen_audicion}</div>'
            '</div>'
            '</section>'
        )

    return (
        '<section class="panel audiometria-panel">'
        '<div class="panel-header">Audiometría por frecuencia</div>'
        f'<p class="audiometria-nota">{pie} Este equipo no registra niveles calibrados en dB HL, '
        'por lo que el gráfico describe respuestas y no umbrales auditivos.</p>'
        '<div class="audiometria-grid">'
        f'{_ear_svg("Oído derecho", derecha, "#dc2626", "circulo")}'
        f'{_ear_svg("Oído izquierdo", izquierda, "#1d4ed8", "cruz")}'
        '</div>'
        '<div class="audiometria-legend">'
        '<span><i class="legend-marker right"></i>Estímulo en oído derecho (círculo)</span>'
        '<span><i class="legend-marker left"></i>Estímulo en oído izquierdo (cruz)</span>'
        '</div></section>'
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
    fecha_nacimiento = getattr(paciente, "fecha_nacimiento", None)
    if isinstance(fecha_nacimiento, datetime):
        fecha_nacimiento = fecha_nacimiento.date()
    if isinstance(fecha_nacimiento, date):
        fecha_nacimiento = fecha_nacimiento.strftime("%d/%m/%Y")
    elif fecha_nacimiento:
        fecha_nacimiento = str(fecha_nacimiento)

    datos_paciente = [
        ["Nombre Completo", nombre or NO_REGISTRADO],
        ["DNI", getattr(paciente, "dni", None) or NO_REGISTRADO],
        ["Fecha de nacimiento", fecha_nacimiento or NO_REGISTRADO],
        ["Fecha/Hora", ahora.strftime("%d/%m/%Y %H:%M")],
        ["Edad", _edad(paciente)],
        ["Correo", correo or NO_REGISTRADO],
        ["Teléfono", getattr(paciente, "telefono", None) or NO_REGISTRADO],
    ]

    registros_oido = por_modulo.get("oido")
    datos_oido = registros_oido[-1].get("data") if registros_oido else {}
    registro_oido = registros_oido[-1] if registros_oido else {}
    resultados_auditivos = _resultados_reales_oido(
        datos_oido, registro_oido.get("origen")
    )
    mediciones = []
    if resultados_auditivos:
        frecuencias = resultados_auditivos["frecuencias_hz"]
        mediciones = [
            [
                "Frecuencias evaluadas",
                ", ".join(str(frecuencia) for frecuencia in frecuencias) + " Hz",
            ]
        ]
        for etiqueta, campo in (
            ("Respuesta oído derecho", "resultados_oido_derecho"),
            ("Respuesta oído izquierdo", "resultados_oido_izquierdo"),
        ):
            valores = resultados_auditivos[campo]
            resumen = "; ".join(
                f"{frecuencia} Hz: "
                f"{'Sí' if valor is True else 'No' if valor is False else 'Sin respuesta'}"
                for frecuencia, valor in zip(frecuencias, valores)
            )
            mediciones.append([etiqueta, resumen])
        if resultados_auditivos["origen"]:
            mediciones.append(["Origen registrado", resultados_auditivos["origen"]])
        if datos_oido.get("nivel_senal") == "REDUCIDO_POR_AUTOINFORME":
            mediciones.append(
                [
                    "Ajuste aplicado por autoinforme",
                    "Volumen digital reducido; no es una medición acústica calibrada",
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
        "resultados_auditivos": resultados_auditivos,
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
.resultados-nota {
  margin: 12px 0 0;
  padding: 9px 11px;
  border-left: 3px solid #d97706;
  border-radius: 0 7px 7px 0;
  color: #713f12;
  background: #fffbeb;
  font-size: 11px;
  line-height: 1.5;
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
.audiometria-ear {
  min-width: 0;
  background: #ffffff;
  border: 1px solid #dfe7f5;
  border-radius: 12px;
  padding: 14px 10px 8px;
}
.audiometria-header {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  text-align: center;
  color: #dc2626;
}
.audiometria-header.izquierdo {
  color: #1d4ed8;
}
.audiometria-ear svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}
.audiometria-detalle {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
}
.audiometria-detalle h3 {
  margin: 0 0 8px;
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.audiometria-frecuencias {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(68px, 1fr));
  gap: 6px;
}
.freq-box {
  min-width: 0;
  padding: 6px 4px;
  border: 1px solid #dbe3eb;
  border-radius: 7px;
  color: #475569;
  background: #f8fafc;
  font-size: 10px;
  line-height: 1.35;
  text-align: center;
  overflow-wrap: anywhere;
}
.freq-box strong {
  display: block;
  margin-bottom: 2px;
  color: #1e293b;
  font-size: 10px;
}
.freq-box.correcta, .freq-box.percibido {
  border-color: #a7dfbd;
  color: #166534;
  background: #f0fdf4;
}
.freq-box.lado-opuesto {
  border-color: #f2d18b;
  color: #854d0e;
  background: #fffbeb;
}
.freq-box.no-escuche, .freq-box.no-percibido {
  border-color: #f3b4b4;
  color: #991b1b;
  background: #fef2f2;
}
.audicion-resumen {
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px solid #e2e8f0;
}
.audicion-leyenda {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
  color: #475569;
  font-size: 10px;
}
.audicion-leyenda span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.audicion-indicador {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: #58b987;
}
.audicion-indicador.no {
  background: #e45b63;
}
.audicion-resultados {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(54px, 1fr));
  gap: 6px;
}
.audicion-frecuencia {
  padding: 5px 3px;
  border: 1px solid #dbe3eb;
  border-radius: 6px;
  color: #475569;
  background: #f8fafc;
  font-size: 9px;
  line-height: 1.3;
  text-align: center;
}
.audicion-frecuencia strong {
  display: block;
  color: #1e293b;
  font-size: 9px;
}
.audicion-frecuencia.si {
  border-color: #a7dfbd;
  color: #166534;
  background: #f0fdf4;
}
.audicion-frecuencia.no {
  border-color: #f3b4b4;
  color: #991b1b;
  background: #fef2f2;
}
.audiometria-legend {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 16px;
  margin: 14px 0 0;
  font-size: 11px;
  color: #475569;
}
.audiometria-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-marker {
  display: inline-block;
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  border: 2px solid currentColor;
  border-radius: 50%;
}
.legend-marker.right { color: #dc2626; background: #dc2626; }
.legend-marker.left {
  border: 0;
  border-radius: 0;
  background:
    linear-gradient(45deg, transparent 42%, #1d4ed8 43%, #1d4ed8 57%, transparent 58%),
    linear-gradient(-45deg, transparent 42%, #1d4ed8 43%, #1d4ed8 57%, transparent 58%);
}
.audiometria-nota {
  margin: -.25rem 0 1rem;
  padding: .7rem .85rem;
  border-left: 3px solid #d97706;
  border-radius: 0 7px 7px 0;
  color: #713f12;
  background: #fffbeb;
  font-size: 12px;
  line-height: 1.5;
}
@media (max-width: 520px) {
  .audiometria-grid { grid-template-columns: 1fr; }
  .audiometria-frecuencias { grid-template-columns: repeat(3, minmax(0, 1fr)); }
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
    bloque_mediciones = (
        '<section class="panel">'
        '<div class="panel-header">Resultados reales registrados · Audiometría</div>'
        f'<div class="metric-grid">{mediciones_grid}</div>'
        '<p class="resultados-nota">“Sí” indica que la persona reportó percibir el tono; '
        '“No” indica que seleccionó “No escuché”. Son respuestas de la prueba, '
        'no umbrales auditivos clínicos.</p>'
        '</section>'
        if reporte["mediciones"]
        else ""
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
        f'{bloque_mediciones}'
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