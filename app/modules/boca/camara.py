import customtkinter as ctk
from tkinter import messagebox
import cv2
from PIL import Image
import numpy as np
import json
import datetime
import requests
import os

# =========================================================
# 1. CONFIGURACION Y COLORES
# =========================================================
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

COLOR_TEXTO_TITULO = "#0A2540"
COLOR_TEXTO_CUERPO = "#1E293B"
COLOR_BOTON_PRI = "#0284C7"

# Colores de Triaje
COLOR_VERDE = "#10B981"
COLOR_AMARILLO = "#F59E0B"
COLOR_ROJO = "#EF4444"

# =========================================================
# 2. VARIABLES DE LA CAMARA Y ESTADO AUTOMATICO
# =========================================================
camara = None
trabajo_camara = None
analisis_realizado = False
ultimo_frame_capturado = None

fase_sistema = 0  # 0 = Esperando posición, 1 a 4 = Fases, 5 = Pantalla de Reporte
progreso_contador = 0
marcos_estables_deteccion = 0

# =========================================================
# 3. ENVIO AUTOMATICO A FASTAPI
# =========================================================


API_URL = "http://127.0.0.1:8000/api/v1/boca/resultados"

EPISODIO_ID = 1
DISPOSITIVO_ID = 1

def enviar_json_automatico(json_str):
    """Envía el informe completo del escáner a FastAPI."""

    try:
        reporte = json.loads(json_str)

        payload = {
            "episodio_id": EPISODIO_ID,
            "dispositivo_id": DISPOSITIVO_ID,
            "origen": "SIMULADOR",
            "data": {
                "sistema": reporte["sistema"],
                "timestamp": reporte["timestamp"],
                "triaje": reporte["triaje"],
                "metricas_tecnicas": reporte["metricas_tecnicas"],
                "analisis_de_causas": reporte["analisis_de_causas"],
                "recomendacion": reporte["recomendacion"]
            }
        }

        respuesta = requests.post(
            API_URL,
            json=payload,
            timeout=10
        )

        respuesta.raise_for_status()

        print("¡Informe completo guardado en FastAPI!")
        print("Respuesta:", respuesta.json())

    except requests.HTTPError as error:
        print("Error HTTP:", error)
        print("Detalle de FastAPI:", error.response.text)

    except (requests.RequestException, ValueError, KeyError) as error:
        print("Error al enviar el resultado:", error)

    
# =========================================================
# 4. GESTION DE PANTALLAS (VISTAS)
# =========================================================
def mostrar_vista_escanner():
    vista_resultados.place_forget()
    vista_escanner.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.92)

def mostrar_vista_resultados(triaje, color_hex, causas, recomendacion, metricas):
    vista_escanner.place_forget()
    
    etiqueta_triaje_resultado.configure(text=f"ESTADO DE TRIAJE: {triaje}", fg_color=color_hex)
    
    caja_causas.configure(state="normal")
    caja_causas.delete("0.0", "end")
    caja_causas.insert("0.0", causas)
    caja_causas.configure(state="disabled")

    caja_rec.configure(state="normal")
    caja_rec.delete("0.0", "end")
    caja_rec.insert("0.0", recomendacion)
    caja_rec.configure(state="disabled")

    texto_metricas = (
        f"• Nitidez (Laplaciano): {metricas['nitidez_laplaciano']}\n"
        f"• Brillo Promedio: {metricas['brillo_promedio']}\n"
        f"• Contraste Profundo: {metricas['contraste_profundo_porcentaje']}%\n"
        f"• Colorimetría RGB -> Rojo: {metricas['colorimetria_rgb']['rojo']} | "
        f"Verde: {metricas['colorimetria_rgb']['verde']} | "
        f"Azul: {metricas['colorimetria_rgb']['azul']}"
    )
    caja_metricas.configure(state="normal")
    caja_metricas.delete("0.0", "end")
    caja_metricas.insert("0.0", texto_metricas)
    caja_metricas.configure(state="disabled")

    vista_resultados.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.92, relheight=0.92)


# =========================================================
# 5. FUNCIONES DE VISION CON INTERFAZ PROFESIONAL
# =========================================================
def encender_camara():
    global camara, trabajo_camara, analisis_realizado, fase_sistema, progreso_contador, marcos_estables_deteccion

    if camara is not None and camara.isOpened():
        return

    for indice in [0, 1, 2, 3]:
        prueba = cv2.VideoCapture(indice, cv2.CAP_DSHOW)

        if not prueba.isOpened():
            prueba.release()
            continue

        prueba.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        prueba.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        ret = False
        frame = None

        for _ in range(10):
            ret, frame = prueba.read()
            if ret and frame is not None:
                break

        if ret and frame is not None:
            camara = prueba
            analisis_realizado = False
            fase_sistema = 0
            progreso_contador = 0
            marcos_estables_deteccion = 0

            mostrar_vista_escanner()
            actualizar_camara()
            return

        prueba.release()

    camara = None
    messagebox.showerror("Error de cámara", "No se pudo obtener imagen de la cámara.\n\n1. Revisa la conexión USB.")


def dibujar_interfaz_profesional(img, texto_estado, color_rgb, porcentaje):
    h, w, _ = img.shape
    x1, y1, x2, y2 = w // 4, h // 4, 3 * w // 4, 3 * h // 4

    longitud_esquina = 30
    grosor = 2
    cv2.line(img, (x1, y1), (x1 + longitud_esquina, y1), color_rgb, grosor)
    cv2.line(img, (x1, y1), (x1, y1 + longitud_esquina), color_rgb, grosor)
    cv2.line(img, (x2, y1), (x2 - longitud_esquina, y1), color_rgb, grosor)
    cv2.line(img, (x2, y1), (x2, y1 + longitud_esquina), color_rgb, grosor)
    cv2.line(img, (x1, y2), (x1 + longitud_esquina, y2), color_rgb, grosor)
    cv2.line(img, (x1, y2), (x1, y2 - longitud_esquina), color_rgb, grosor)
    cv2.line(img, (x2, y2), (x2 - longitud_esquina, y2), color_rgb, grosor)
    cv2.line(img, (x2, y2), (x2, y2 - longitud_esquina), color_rgb, grosor)

    overlay = img.copy()
    cv2.rectangle(overlay, (15, 15), (w - 15, 65), (15, 23, 42), -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    cv2.putText(img, "ODONTO-SCANNER AI | SISTEMA CLINICO INTELIGENTE", (25, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (148, 163, 184), 1)
    cv2.putText(img, texto_estado, (25, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color_rgb, 2)

    if porcentaje > 0:
        cv2.rectangle(img, (15, h - 35), (w - 15, h - 15), (30, 41, 59), -1)
        ancho_barra = int((w - 35) * (porcentaje / 100))
        cv2.rectangle(img, (18, h - 32), (18 + ancho_barra, h - 18), color_rgb, -1)
        cv2.putText(img, f"PROGRESO DE ANALISIS: {porcentaje}%", (25, h - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)

    return img


def procesar_vision_automatica(frame):
    global mensaje_estado_automatico, analisis_realizado, ultimo_frame_capturado, fase_sistema, progreso_contador, marcos_estables_deteccion

    if analisis_realizado or fase_sistema == 5:
        return frame

    ultimo_frame_capturado = frame.copy()
    h, w, _ = frame.shape

    roi = frame[h//4:3*h//4, w//4:3*w//4]
    gris_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    brillo_actual = np.mean(gris_roi)
    nitidez_actual = cv2.Laplacian(gris_roi, cv2.CV_64F).var()

    zoom_auto = 1.35
    nuevo_h, nuevo_w = int(h / zoom_auto), int(w / zoom_auto)
    y1_z, x1_z = (h - nuevo_h) // 2, (w - nuevo_w) // 2
    recorte_zoom = frame[y1_z:y1_z+nuevo_h, x1_z:x1_z+nuevo_w]
    frame_procesado = cv2.resize(recorte_zoom, (w, h), interpolation=cv2.INTER_LINEAR)

    hsv = cv2.cvtColor(frame_procesado, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([12, 40, 40])
    upper_yellow = np.array([38, 255, 255])
    mascara_amarillo = cv2.inRange(hsv, lower_yellow, upper_yellow)

    gris_total = cv2.cvtColor(frame_procesado, cv2.COLOR_BGR2GRAY)
    bw = cv2.cvtColor(gris_total, cv2.COLOR_GRAY2BGR)
    mascara_3ch = cv2.cvtColor(mascara_amarillo, cv2.COLOR_GRAY2BGR) > 0
    base_visual = np.where(mascara_3ch, frame_procesado, bw)

    texto_estado = ""
    color_rgb = (0, 165, 255)
    porcentaje = 0

    if fase_sistema == 0:
        texto_estado = ">> ACERQUE LA BOCA AL CUADRADO Y ABRA LA BOCA <<"
        if brillo_actual >= 40 and nitidez_actual >= 10:
            marcos_estables_deteccion += 1
            if marcos_estables_deteccion >= 25:
                fase_sistema = 1
                progreso_contador = 0
        else:
            marcos_estables_deteccion = 0

    elif fase_sistema == 1:
        if brillo_actual < 40:
            texto_estado = "[FASE 1/4] AUMENTE LA LUZ O ACERCE LA BOCA"
            color_rgb = (0, 0, 255)
        else:
            progreso_contador += 1
            porcentaje = int((progreso_contador / 45) * 25)
            texto_estado = f"[FASE 1/4] Verificando iluminación ambiental..."
            color_rgb = (0, 165, 255)
            if progreso_contador >= 45:
                progreso_contador = 0
                fase_sistema = 2

    elif fase_sistema == 2:
        if nitidez_actual < 12:
            texto_estado = "[FASE 2/4] MANTENGA FIRME LA CÁMARA (EVITE MOVERSE)"
            color_rgb = (0, 0, 255)
        else:
            progreso_contador += 1
            porcentaje = 25 + int((progreso_contador / 45) * 25)
            texto_estado = f"[FASE 2/4] Analizando enfoque y nitidez óptica..."
            color_rgb = (0, 255, 255)
            if progreso_contador >= 45:
                progreso_contador = 0
                fase_sistema = 3

    elif fase_sistema == 3:
        progreso_contador += 1
        porcentaje = 50 + int((progreso_contador / 45) * 25)
        texto_estado = f"[FASE 3/4] Mapeando texturas y espacios interdentales..."
        color_rgb = (0, 140, 255)
        if progreso_contador >= 45:
            progreso_contador = 0
            fase_sistema = 4

    elif fase_sistema == 4:
        progreso_contador += 1
        porcentaje = 75 + int((progreso_contador / 45) * 25)
        texto_estado = f"[FASE 4/4] Extrayendo colorimetría y generando triaje..."
        color_rgb = (0, 255, 0)
        if progreso_contador >= 45:
            analisis_realizado = True
            app.after(100, ejecutar_analisis_y_cambiar_pagina)

    return dibujar_interfaz_profesional(base_visual, texto_estado, color_rgb, porcentaje)


def ejecutar_analisis_y_cambiar_pagina():
    global ultimo_frame_capturado, fase_sistema

    if ultimo_frame_capturado is None:
        return

    fase_sistema = 5
    h, w, _ = ultimo_frame_capturado.shape
    roi = ultimo_frame_capturado[h//4:3*h//4, w//4:3*w//4]

    media_b, media_g, media_r, _ = cv2.mean(roi)
    gris_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    brillo_promedio = np.mean(gris_roi)
    nitidez = cv2.Laplacian(gris_roi, cv2.CV_64F).var()

    pixeles_oscuros = np.sum(gris_roi < (brillo_promedio * 0.55))
    porcentaje_oscuros = (pixeles_oscuros / gris_roi.size) * 100

    lista_causas = []
    if porcentaje_oscuros > 18:
        lista_causas.append("• Presencia de contrastes profundos elevados (espacios interdentales o acumulación superficial).")
    if media_r > (media_g + 22):
        lista_causas.append("• Saturación elevada en tonos rojizos, sugiriendo posible irritación o inflamación gingival.")
    
    if not lista_causas:
        lista_causas.append("• Ninguna anomalía significativa detectada en la superficie analizada.")
        analisis_causas_texto = "Estructura visual homogénea y estable tras el escaneo autónomo."
    else:
        analisis_causas_texto = "Factores identificados tras el análisis detallado:\n" + "\n".join(lista_causas)

    if porcentaje_oscuros > 18 or media_r > (media_g + 22):
        estado_triaje = "AMARILLO"
        descripcion_triaje = "Precaución / Hallazgos a Revisar"
        color_hex = COLOR_AMARILLO
        recomendacion = "Reforzar la higiene interdental y programar revisión preventiva."
    else:
        estado_triaje = "VERDE"
        descripcion_triaje = "Saludable / Parámetros Óptimos"
        color_hex = COLOR_VERDE
        recomendacion = "Sin alertas visuales marcadas. Mantener los hábitos adecuados de higiene bucal."

    metricas_dict = {
        "nitidez_laplaciano": round(float(nitidez), 2),
        "brillo_promedio": round(float(brillo_promedio), 2),
        "contraste_profundo_porcentaje": round(float(porcentaje_oscuros), 2),
        "colorimetria_rgb": {
            "rojo": round(float(media_r), 2),
            "verde": round(float(media_g), 2),
            "azul": round(float(media_b), 2)
        }
    }

    reporte_dict = {
        "sistema": "OdontoScanner AI",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "triaje": {
            "nivel": estado_triaje,
            "detalle": descripcion_triaje
        },
        "metricas_tecnicas": metricas_dict,
        "analisis_de_causas": analisis_causas_texto,
        "recomendacion": recomendacion
    }

    json_resultado = json.dumps(reporte_dict, indent=4, ensure_ascii=False)
    enviar_json_automatico(json_resultado)

    if trabajo_camara is not None:
        try:
            app.after_cancel(trabajo_camara)
        except Exception:
            pass

    mostrar_vista_resultados(estado_triaje, color_hex, analisis_causas_texto, recomendacion, metricas_dict)


def reiniciar_para_siguiente_paciente():
    global analisis_realizado, fase_sistema, progreso_contador, marcos_estables_deteccion
    analisis_realizado = False
    fase_sistema = 0
    progreso_contador = 0
    marcos_estables_deteccion = 0
    encender_camara()


def actualizar_camara():
    global trabajo_camara, fase_sistema

    if fase_sistema == 5 or camara is None or not camara.isOpened():
        return

    ret, frame = camara.read()

    if ret and frame is not None:
        frame = procesar_vision_automatica(frame)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        imagen = Image.fromarray(frame)
        imagen.thumbnail((480, 350))

        foto = ctk.CTkImage(
            light_image=imagen,
            dark_image=imagen,
            size=imagen.size
        )

        etiqueta_camara.configure(image=foto, text="")
        etiqueta_camara.image = foto
    else:
        etiqueta_camara.configure(text="Esperando imagen de la cámara...")

    trabajo_camara = app.after(30, actualizar_camara)


def cerrar_aplicacion():
    global camara, trabajo_camara
    if trabajo_camara is not None:
        try:
            app.after_cancel(trabajo_camara)
        except Exception:
            pass
    if camara is not None:
        camara.release()
    app.destroy()


# =========================================================
# 6. INTERFAZ GRAFICA CON FONDO TEMATICO VISIBLE
# =========================================================
app = ctk.CTk()
app.title("Sistema Odontológico Profesional - OdontoScanner")
app.geometry("680x760")
app.minsize(580, 700)
app.configure(fg_color="#FFFFFF")

# 1. Cargar y colocar la imagen de fondo temática detrás de todo
nombre_archivo_fondo = "fondo_dental.png"  # Asegúrate de que tu imagen se llame así en la carpeta

if os.path.exists(nombre_archivo_fondo):
    imagen_pil = Image.open(nombre_archivo_fondo)
    fondo_ctk = ctk.CTkImage(light_image=imagen_pil, dark_image=imagen_pil, size=(680, 760))
    label_fondo = ctk.CTkLabel(app, image=fondo_ctk, text="")
    label_fondo.place(x=0, y=0, relwidth=1, relheight=1)
else:
    print(f"[AVISO] No se encontró '{nombre_archivo_fondo}'. Colócala en la carpeta del proyecto.")

# --- PÁGINA 1: VISTA DE ESCANEO PROFESIONAL (Con fondo semitransparente/blanco translúcido) ---
vista_escanner = ctk.CTkFrame(master=app, fg_color="#FFFFFF", corner_radius=16, border_width=1, border_color="#CBD5E1")

ctk.CTkLabel(vista_escanner, text="Escáner Odontológico Inteligente", font=("Roboto", 20, "bold"), text_color=COLOR_TEXTO_TITULO).pack(pady=(12, 2))
ctk.CTkLabel(vista_escanner, text="Posicione al paciente. El sistema detectará el inicio automáticamente...", font=("Roboto", 12), text_color=COLOR_TEXTO_CUERPO).pack(pady=(0, 8))

etiqueta_camara = ctk.CTkLabel(vista_escanner, text="Iniciando cámara...", width=480, height=350, fg_color="#1E293B", corner_radius=10)
etiqueta_camara.pack(padx=15, pady=5)


# --- PÁGINA 2: VISTA DE RESULTADOS COMPLETOS ---
vista_resultados = ctk.CTkFrame(master=app, fg_color="#FFFFFF", corner_radius=16, border_width=1, border_color="#CBD5E1")

ctk.CTkLabel(vista_resultados, text="Informe Clínico y Diagnóstico", font=("Roboto", 18, "bold"), text_color=COLOR_TEXTO_TITULO).pack(pady=(12, 5))

etiqueta_triaje_resultado = ctk.CTkLabel(vista_resultados, text="ESTADO DE TRIAJE", font=("Roboto", 14, "bold"), text_color="#FFFFFF", corner_radius=8, height=35)
etiqueta_triaje_resultado.pack(pady=5, padx=20, fill="x")

ctk.CTkLabel(vista_resultados, text="Análisis de Causas:", font=("Roboto", 11, "bold"), text_color=COLOR_TEXTO_CUERPO).pack(anchor="w", padx=25, pady=(5, 2))
caja_causas = ctk.CTkTextbox(vista_resultados, width=540, height=75, corner_radius=6, border_width=1, border_color="#CBD5E1", font=("Roboto", 11))
caja_causas.pack(padx=20, pady=2)

ctk.CTkLabel(vista_resultados, text="Métricas Técnicas Capturadas:", font=("Roboto", 11, "bold"), text_color=COLOR_TEXTO_CUERPO).pack(anchor="w", padx=25, pady=(5, 2))
caja_metricas = ctk.CTkTextbox(vista_resultados, width=540, height=75, corner_radius=6, border_width=1, border_color="#CBD5E1", font=("Consolas", 11))
caja_metricas.pack(padx=20, pady=2)

ctk.CTkLabel(vista_resultados, text="Recomendación:", font=("Roboto", 11, "bold"), text_color=COLOR_TEXTO_CUERPO).pack(anchor="w", padx=25, pady=(5, 2))
caja_rec = ctk.CTkTextbox(vista_resultados, width=540, height=55, corner_radius=6, border_width=1, border_color="#CBD5E1", font=("Roboto", 11))
caja_rec.pack(padx=20, pady=2)

ctk.CTkButton(
    vista_resultados, text="Volver a Escanear Siguiente Paciente", fg_color=COLOR_BOTON_PRI, 
    command=reiniciar_para_siguiente_paciente, height=38, width=280, font=("Roboto", 12, "bold")
).pack(pady=12)


# =========================================================
# 7. CIERRE SEGURO Y AUTORRUN
# =========================================================
app.protocol("WM_DELETE_WINDOW", cerrar_aplicacion)

if __name__ == "__main__":
    app.after(200, encender_camara)
    app.mainloop()