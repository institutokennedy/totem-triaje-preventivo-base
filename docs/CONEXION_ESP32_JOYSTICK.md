# Conexión y puesta en marcha del joystick con ESP32

El proyecto ya incluye un programa en MicroPython en `app/hardware/main.py`.
El ESP32 lee el eje horizontal del joystick y envía `"IZQUIERDO"` o `"DERECHO"`
a la API. Al presionar hacia abajo el botón del stick, envía `"NO_ESCUCHE"`. El navegador
reproduce los tonos, elegidos de manera aleatoria a izquierda o derecha, y recoge
las respuestas. Los botones de pantalla siguen disponibles como respaldo.

Esta guía asume una placa ESP32 clásica (por ejemplo ESP32 DevKit/WROOM) y un
joystick analógico con pines `GND`, `VCC`, `VRx`, `VRy` y `SW`. Otras variantes
de ESP32 pueden tener otro mapa de pines.

## Cableado

Conecta la placa apagada y usa sus pines `3V3` y `GND` para alimentar el módulo.
Si usas los rieles de la protoboard, lleva `3V3` al riel positivo y `GND` al
riel negativo.

| Joystick | ESP32 | Uso |
|---|---|---|
| `GND` | `GND` | Tierra común |
| `VCC` | `3V3` | Alimentación del joystick |
| `VRy` | Sin conectar | Eje vertical no utilizado |
| `VRx` | `GPIO35` | Eje horizontal leído por el programa |
| `SW` | `GPIO27` | Pulsador; se activa al presionar el stick |

**No conectes `VCC` a `5V`/`VIN`**: la salida analógica del joystick podría
superar el voltaje permitido en la entrada del ESP32. El programa usa `GPIO35`,
una entrada ADC1 apta para este uso y compatible con Wi-Fi en el ESP32 clásico.
El botón se configura con la resistencia `PULL_UP` interna: al presionarlo debe
conectar `SW` a `GND`, no a `3V3`.

## Preparar el programa y la red

1. Instala MicroPython en la placa si todavía no lo tiene.
2. En `app/hardware/config.py`, configura `WIFI_SSID` y `WIFI_PASSWORD` con una
   red **de 2,4 GHz**. Un ESP32 clásico no puede conectarse a una red de 5 GHz.
   No publiques ni subas tus credenciales.
3. En `SERVER_URL`, escribe la dirección IPv4 del equipo que ejecutará FastAPI,
   por ejemplo `http://192.168.1.50:8000`. Obtén la dirección con `ipconfig`
   en Windows; no uses `127.0.0.1` ni `localhost` en la configuración del ESP32.
4. Conecta el equipo y el ESP32 a la misma red local. Inicia FastAPI para que
   escuche en la red:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   Permite el acceso de Python/Uvicorn en la red privada si el firewall de
   Windows lo solicita.
5. Copia `app/hardware/main.py` y `app/hardware/config.py` a la raíz del sistema
   de archivos del ESP32 como `main.py` y `config.py`. Puedes usar Thonny o
   `mpremote`. Reinicia la placa con el joystick en reposo y abre el monitor
   serial a 115200 baudios.
6. El monitor serial debe mostrar la conexión Wi-Fi, la dirección IP del ESP32,
   un `dispositivo_id` y el mensaje de que está esperando respuestas. Al iniciar,
   el programa calibra el centro del joystick: no lo muevas durante ese momento.
7. Abre la aplicación en el navegador, inicia la evaluación auditiva y pulsa
   **Comenzar**. Para cada tono, mueve el joystick a la izquierda o derecha según
   el lado donde crees haberlo escuchado. Si no oyes nada, presiona hacia abajo
   el botón del joystick. Las opciones de respuesta en pantalla quedan disponibles como
   respaldo.

## Comprobación y ajustes

- Si izquierda y derecha quedan intercambiadas, cambia `INVERTIR_EJE_X` a `True` en
  `config.py` y reinicia el ESP32.
- Si un movimiento no se reconoce, comprueba el cable de `VRx`, la tierra común
  y que el joystick vuelva al centro. La sensibilidad se ajusta con
  `UMBRAL_DESVIO`.
- Si no se registra la pulsación, comprueba el cable entre `SW` y `GPIO27` y la
  tierra común; el programa confirma la pulsación y espera a que se suelte antes
  de aceptar otro evento.
- Si no aparece `WiFi OK`, revisa que la red sea 2,4 GHz y que SSID y clave sean
  correctos.
- Si el ESP32 no puede contactar al servidor, revisa `SERVER_URL`, la red local
  y el firewall. La página y el ESP32 deben llegar al mismo servidor FastAPI.
- El buffer de respuestas está en memoria: ejecuta Uvicorn con un solo proceso
  (no uses varios `--workers` para este flujo).

Use auriculares estéreo: si el navegador o el equipo no admite separación
estéreo, la página detendrá el inicio en lugar de emitir el tono por ambos lados.
La respuesta del joystick es una entrada de demostración y no es una medición
clínica ni calibra el volumen de los tonos.
