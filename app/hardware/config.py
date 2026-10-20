# Configuración del ESP32 - Módulo de Oído (copiar junto a main.py en la placa)

# --- Red ---
WIFI_SSID = "Fibertel WiFi604 5.8GHz"
WIFI_PASSWORD = "24356627"

# IP del equipo que corre FastAPI (iniciar con: uvicorn app.main:app --host 0.0.0.0 --port 8000)
SERVER_URL = "http://192.168.1.50:8000"

# --- Identificación ---
CODIGO_DISPOSITIVO = "OIDO-001"
NOMBRE_DISPOSITIVO = "Audiometría"
TIPO_DISPOSITIVO = "OIDO"
ORIGEN = "ESP32"

# --- Joystick analógico (solo eje vertical) ---
PIN_JOY_Y = 34              # eje Y (VRy). Usar un pin ADC1 (32-39): ADC2 no funciona con WiFi
INVERTIR_EJE_Y = False      # False: valor ADC alto = ARRIBA. Poner True si "arriba" se detecta como "abajo"
UMBRAL_DESVIO = 0.25        # fracción del rango ADC que hay que desviar desde el centro (0.1-0.5)
TIEMPO_CONFIRMACION_MS = 80 # tiempo mínimo sosteniendo el movimiento para validarlo

# --- Comunicación ---
INTENTOS_ENVIO = 3
TIMEOUT_WIFI_S = 20