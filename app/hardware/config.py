# Configuración del ESP32 - Módulo de Oído (copiar junto a main.py en la placa)

# --- Red ---
WIFI_SSID = "CAMBIAR_POR_RED_WIFI_2_4_GHZ"
WIFI_PASSWORD = "CAMBIAR_POR_CLAVE_WIFI"

# IP del equipo que corre FastAPI (iniciar con: uvicorn app.main:app --host 0.0.0.0 --port 8000)
SERVER_URL = "http://CAMBIAR_POR_IP_DEL_SERVIDOR:8000"

# --- Identificación ---
CODIGO_DISPOSITIVO = "OIDO-001"
NOMBRE_DISPOSITIVO = "Audiometría"
TIPO_DISPOSITIVO = "OIDO"
ORIGEN = "ESP32"

# --- Joystick analógico (eje horizontal) ---
PIN_JOY_X = 35              # eje X (VRx). Usar un pin ADC1 (32-39): ADC2 no funciona con WiFi
PIN_JOY_SW = 27             # pulsador (SW), activo en LOW y con resistencia pull-up interna
INVERTIR_EJE_X = False      # False: valor ADC alto = DERECHA. Poner True si los lados quedan invertidos
UMBRAL_DESVIO = 0.25        # fracción del rango ADC que hay que desviar desde el centro (0.1-0.5)
TIEMPO_CONFIRMACION_MS = 80 # tiempo mínimo sosteniendo el movimiento para validarlo

# --- Comunicación ---
INTENTOS_ENVIO = 3
TIMEOUT_WIFI_S = 20