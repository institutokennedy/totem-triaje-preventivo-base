# Configuración del ESP32 - Módulo de Oído (copiar junto a main.py en la placa)

# --- Red ---
WIFI_SSID = "Fibertel WiFi604 5.8GHz"
WIFI_PASSWORD = "24356627"

# IP del equipo que corre FastAPI (iniciar con: uvicorn app.main:app --host 0.0.0.0 --port 8000)
SERVER_URL = "http://192.168.1.50:8000"

# --- Identificación ---
# Episodio activo en el software (debe existir en la BD, si no la API responde 404).
EPISODIO_ID = 1
CODIGO_DISPOSITIVO = "OIDO-001"
NOMBRE_DISPOSITIVO = "Audiometría"
TIPO_DISPOSITIVO = "OIDO"
ORIGEN = "ESP32"

# --- Pines (GPIO) ---
PIN_SALIDA_DERECHO = 25     # canal de audio derecho (buzzer/auricular + resistencia)
PIN_SALIDA_IZQUIERDO = 26   # canal de audio izquierdo
PIN_BOTON_DERECHO = 32      # botón "escuché del lado derecho" (a GND, pull-up interno)
PIN_BOTON_IZQUIERDO = 33    # botón "escuché del lado izquierdo" (a GND, pull-up interno)
PIN_LED = 2                 # LED integrado

# --- Prueba ---
FRECUENCIAS_HZ = [500, 1000, 2000, 4000]
DURACION_TONO_MS = 1500        # tiempo que suena el tono
VENTANA_RESPUESTA_MS = 3500    # tiempo total para responder (incluye el tono)
PAUSA_ENTRE_TONOS_MS = 800
VOLUMEN_PORCENTAJE = 50        # ciclo de trabajo del PWM (1-50); calibrar con el hardware real

# --- Comunicación ---
INTENTOS_ENVIO = 3
TIMEOUT_WIFI_S = 20