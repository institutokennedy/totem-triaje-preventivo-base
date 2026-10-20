"""ESP32 (MicroPython) - Módulo de Oído (solo entrada).

El sonido lo reproduce el software (navegador) por los auriculares de la computadora.
El ESP32 solo lee el joystick analógico:

    joystick ARRIBA  -> "sí escucho"  -> {"respuesta": true}
    joystick ABAJO   -> "no escucho"  -> {"respuesta": false}

y envía cada respuesta como JSON a FastAPI:

  GET  /api/v1/dispositivos        -> busca OIDO-001
  POST /api/v1/dispositivos        -> lo registra si no existe
  POST /api/v1/oido/respuestas     -> {"dispositivo_id": N, "respuesta": bool, "origen": "ESP32"}

El navegador consulta esas respuestas y arma el resultado final del episodio.
No tocar el joystick al encender la placa (se calibra el centro).
"""
import time

import network
import ujson
from machine import ADC, Pin

try:
    import urequests as requests
except ImportError:  # MicroPython reciente trae "requests"
    import requests

import config

HEADERS = {"Content-Type": "application/json"}


# ---------------------------------------------------------------- joystick
class Joystick:
    """Eje Y analógico (ADC1)."""

    def __init__(self, pin_y):
        self.adc = ADC(Pin(pin_y))
        self.adc.atten(ADC.ATTN_11DB)  # rango ~0-3.3 V
        self.centro = 32768
        self.calibrar()

    def _leer(self):
        total = 0
        for _ in range(5):
            total += self.adc.read_u16()
            time.sleep_us(200)
        return total // 5

    def calibrar(self):
        """Toma el centro en reposo (promedio)."""
        total = 0
        for _ in range(30):
            total += self._leer()
            time.sleep_ms(5)
        self.centro = total // 30
        print("Centro del joystick:", self.centro)

    def direccion(self):
        """+1 = arriba, -1 = abajo, 0 = centro."""
        desvio = self._leer() - self.centro
        if config.INVERTIR_EJE_Y:
            desvio = -desvio
        umbral = int(65535 * config.UMBRAL_DESVIO)
        if desvio > umbral:
            return 1
        if desvio < -umbral:
            return -1
        return 0

    def esperar_centro(self):
        while self.direccion() != 0:
            time.sleep_ms(10)

    def esperar_gesto(self):
        """Bloquea hasta que el joystick se sostenga arriba/abajo el tiempo mínimo.

        Devuelve +1 (arriba) o -1 (abajo).
        """
        previo = 0
        desde = None
        while True:
            actual = self.direccion()
            if actual != 0 and actual == previo:
                if time.ticks_diff(time.ticks_ms(), desde) >= config.TIEMPO_CONFIRMACION_MS:
                    return actual
            else:
                desde = time.ticks_ms() if actual != 0 else None
            previo = actual
            time.sleep_ms(5)


joystick = Joystick(config.PIN_JOY_Y)


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


def enviar_respuesta(dispositivo_id, escucho):
    """POST /api/v1/oido/respuestas. Devuelve True si la API responde 201."""
    payload = {
        "dispositivo_id": dispositivo_id,
        "respuesta": escucho,
        "origen": config.ORIGEN,
    }
    for intento in range(1, config.INTENTOS_ENVIO + 1):
        try:
            conectar_wifi()
            resp = requests.post(
                _url("/api/v1/oido/respuestas"),
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
        time.sleep_ms(300)
    return False


def preparar():
    """Conecta a WiFi y obtiene dispositivo_id; reintenta hasta lograrlo."""
    while True:
        try:
            conectar_wifi()
            return obtener_dispositivo_id()
        except Exception as e:
            print("Error de inicio:", e)
            time.sleep(5)


# ------------------------------------------------------------------- main
def main():
    dispositivo_id = preparar()
    print("dispositivo_id:", dispositivo_id, "- listo, esperando respuestas del joystick")

    while True:
        gesto = joystick.esperar_gesto()
        escucho = gesto == 1  # arriba = sí, abajo = no
        print("Respuesta:", "SI" if escucho else "NO")
        if not enviar_respuesta(dispositivo_id, escucho):
            print("No se pudo enviar la respuesta; el paciente puede repetir el movimiento.")
        joystick.esperar_centro()


main()