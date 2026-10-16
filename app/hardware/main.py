"""ESP32 (MicroPython) - Módulo de Oído.

Emite tonos por dos canales (derecho / izquierdo), lee dos botones
(uno por oído), arma el JSON y lo envía a FastAPI:

  GET  /api/v1/dispositivos          -> busca OIDO-001
  POST /api/v1/dispositivos          -> lo registra si no existe
  POST /api/v1/oido/resultados       -> guarda la medición (espera 201)

Uso: presionar AMBOS botones a la vez para iniciar la prueba.
Requiere MicroPython >= 1.20 (PWM.duty_u16; hay respaldo para duty()).
"""
import time

import network
import ujson
from machine import PWM, Pin

try:
    import urequests as requests
except ImportError:  # MicroPython reciente trae "requests"
    import requests

import config

HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------- hardware
class CanalAudio:
    """Salida de tono por PWM en un pin (un oído)."""

    def __init__(self, pin_num):
        self.pwm = PWM(Pin(pin_num), freq=1000)
        self._duty(0)

    def _duty(self, porcentaje):
        try:
            self.pwm.duty_u16(int(65535 * porcentaje / 100))
        except AttributeError:
            self.pwm.duty(int(1023 * porcentaje / 100))

    def tono(self, frecuencia_hz):
        self.pwm.freq(int(frecuencia_hz))
        self._duty(config.VOLUMEN_PORCENTAJE)

    def silencio(self):
        self._duty(0)


class Boton:
    """Botón a GND con pull-up interno y antirrebote."""

    def __init__(self, pin_num):
        self.pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)

    def presionado(self):
        if self.pin.value() == 0:
            time.sleep_ms(20)  # antirrebote
            return self.pin.value() == 0
        return False

    def esperar_soltar(self):
        while self.pin.value() == 0:
            time.sleep_ms(10)


led = Pin(config.PIN_LED, Pin.OUT)
canal_derecho = CanalAudio(config.PIN_SALIDA_DERECHO)
canal_izquierdo = CanalAudio(config.PIN_SALIDA_IZQUIERDO)
boton_derecho = Boton(config.PIN_BOTON_DERECHO)
boton_izquierdo = Boton(config.PIN_BOTON_IZQUIERDO)


def parpadear(veces, ms=150):
    for _ in range(veces):
        led.value(1)
        time.sleep_ms(ms)
        led.value(0)
        time.sleep_ms(ms)


# -------------------------------------------------------------------- red
def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    inicio = time.time()
    while not wlan.isconnected():
        if time.time() - inicio > config.TIMEOUT_WIFI_S:
            raise RuntimeError("No se pudo conectar a la red WiFi")
        time.sleep_ms(300)
    print("WiFi OK:", wlan.ifconfig()[0])
    return wlan


def _url(ruta):
    return config.SERVER_URL.rstrip("/") + ruta


def _id_de(dispositivo):
    if "id_dispositivo" in dispositivo:
        return dispositivo["id_dispositivo"]
    return dispositivo["id"]


def obtener_dispositivo_id():
    """Busca OIDO-001 en la API; si no existe lo registra con POST."""
    resp = requests.get(_url("/api/v1/dispositivos"))
    try:
        if resp.status_code != 200:
            raise RuntimeError("GET dispositivos respondió %d" % resp.status_code)
        lista = resp.json()
    finally:
        resp.close()

    items = lista if isinstance(lista, list) else lista.get("items", [])
    for d in items:
        if d.get("codigo") == config.CODIGO_DISPOSITIVO:
            return _id_de(d)

    cuerpo = {
        "codigo": config.CODIGO_DISPOSITIVO,
        "nombre": config.NOMBRE_DISPOSITIVO,
        "tipo": config.TIPO_DISPOSITIVO,
    }
    resp = requests.post(
        _url("/api/v1/dispositivos"), data=ujson.dumps(cuerpo), headers=HEADERS
    )
    try:
        if resp.status_code not in (200, 201):
            raise RuntimeError("POST dispositivos respondió %d" % resp.status_code)
        return _id_de(resp.json())
    finally:
        resp.close()


def enviar_resultado(payload):
    """POST /api/v1/oido/resultados. Devuelve True si la API responde 201."""
    for intento in range(1, config.INTENTOS_ENVIO + 1):
        try:
            resp = requests.post(
                _url("/api/v1/oido/resultados"),
                data=ujson.dumps(payload),
                headers=HEADERS,
            )
            codigo = resp.status_code
            resp.close()
            if codigo == 201:
                return True
            print("Servidor respondió", codigo)
            if codigo in (404, 422):  # error de datos: reintentar no ayuda
                return False
        except Exception as e:  # sin red, timeout, etc.
            print("Error de envío (%d): %s" % (intento, e))
        time.sleep(1)
    return False


# ----------------------------------------------------------------- prueba
def probar_tono(canal, boton_propio, boton_otro, frecuencia):
    """Suena un tono en un oído y espera que se presione el botón de ESE lado.

    True  -> presionó su botón dentro de la ventana de respuesta.
    False -> no presionó, o presionó solo el botón del otro lado.
    """
    boton_propio.esperar_soltar()
    boton_otro.esperar_soltar()

    canal.tono(frecuencia)
    inicio = time.ticks_ms()
    escucho = False
    sonando = True

    while time.ticks_diff(time.ticks_ms(), inicio) < config.VENTANA_RESPUESTA_MS:
        if sonando and time.ticks_diff(time.ticks_ms(), inicio) >= config.DURACION_TONO_MS:
            canal.silencio()
            sonando = False
        if boton_propio.presionado():
            escucho = True
            break
        time.sleep_ms(5)

    canal.silencio()
    boton_propio.esperar_soltar()
    time.sleep_ms(config.PAUSA_ENTRE_TONOS_MS)
    return escucho


def ejecutar_prueba():
    """Mide derecho e izquierdo para cada frecuencia y arma el diccionario DatosOido."""
    frecuencias = list(config.FRECUENCIAS_HZ)
    derecho = []
    izquierdo = []

    for f in frecuencias:
        print("Oído derecho,", f, "Hz")
        derecho.append(probar_tono(canal_derecho, boton_derecho, boton_izquierdo, f))
    for f in frecuencias:
        print("Oído izquierdo,", f, "Hz")
        izquierdo.append(probar_tono(canal_izquierdo, boton_izquierdo, boton_derecho, f))

    return {
        "frecuencias_hz": frecuencias,
        "resultados_oido_derecho": derecho,
        "resultados_oido_izquierdo": izquierdo,
    }


def esperar_inicio():
    """Espera que se presionen ambos botones a la vez."""
    print("Presione ambos botones para iniciar...")
    while not (boton_derecho.presionado() and boton_izquierdo.presionado()):
        time.sleep_ms(50)
    boton_derecho.esperar_soltar()
    boton_izquierdo.esperar_soltar()
    parpadear(2)
    time.sleep_ms(500)


# ------------------------------------------------------------------- main
def main():
    parpadear(1)
    conectar_wifi()
    dispositivo_id = obtener_dispositivo_id()
    print("dispositivo_id:", dispositivo_id)

    pendiente = None  # payload no enviado (se reintenta sin repetir la prueba)

    while True:
        esperar_inicio()

        if pendiente is None:
            datos = ejecutar_prueba()
            pendiente = {
                "episodio_id": config.EPISODIO_ID,
                "dispositivo_id": dispositivo_id,
                "origen": config.ORIGEN,
                "data": datos,
            }
            print(ujson.dumps(pendiente))

        try:
            conectar_wifi()
            ok = enviar_resultado(pendiente)
        except Exception as e:
            print("Error:", e)
            ok = False

        if ok:
            print("Resultado guardado (201).")
            parpadear(3)
            pendiente = None
        else:
            print("No se pudo guardar. Presione ambos botones para reintentar el envío.")
            parpadear(6, 80)


main()
