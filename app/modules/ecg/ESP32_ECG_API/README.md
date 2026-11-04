# ESP32 ECG API

Firmware PlatformIO para ESP32 con sensor AD8232. Envía muestras ADC originales al adaptador FastAPI del módulo ECG. No aplica filtros ni genera muestras para completar capturas.

## Hardware verificado en el código

- Entrada analógica AD8232 OUT: GPIO 34 (ADC1_CH6), resolución configurada en 12 bits.
- Lead-off LO+: GPIO 26.
- Lead-off LO-: GPIO 27.
- Frecuencia objetivo: 250 Hz (periodo nominal de 4 ms).
- Captura: 10 s, exactamente 2500 muestras.
- Unidad: cuentas ADC enteras, rango 0–4095. No se convierten a mV.
- Dispositivo del catálogo: código canónico `ECG-001` (ID numérico `1` en la base inspeccionada).

La conexión física y el cableado deben validarse con la placa y el módulo reales antes de uso.

## Configuración

1. Copiá `include/ecg_config.h.example` como `include/ecg_config.h`.
2. Configurá únicamente el SSID y la clave Wi-Fi en ese archivo local. `ecg_config.h` está excluido de Git; no copies credenciales a `main.cpp` ni a archivos versionados.
3. Iniciá FastAPI en una interfaz accesible desde la red local: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`. Si cambiás el puerto, configurá `ECG_API_PORT` con el mismo valor antes de iniciar la aplicación (por ejemplo, en PowerShell: `$env:ECG_API_PORT=8001`).
4. Permití mDNS/DNS-SD multicast (UDP 5353) y HTTP TCP entre el tótem y el ESP32 en la red local. El servidor publica `_totem-api._tcp.local`; el ESP32 lo descubre y obtiene dirección y puerto por mDNS. El ESP32 anuncia `_ecg._tcp.local`; el backend descubre el sensor y el frontend consume esa lista a través de la API del mismo origen.
5. Compilá y cargá desde esta carpeta con PlatformIO (`pio run`, luego `pio run -t upload`). Abrí el monitor serie a 115200 baudios para consultar el estado Wi-Fi y mDNS.
6. Abrí el módulo ECG desde el tótem. La interfaz busca el ESP32 automáticamente y muestra el estado de conexión. Tras verificar episodio, dispositivo y electrodos, elegí **Iniciar ECG** para comenzar la captura.

El episodio se configura explícitamente desde el frontend del tótem y no queda guardado al reiniciar el ESP32. Una captura pendiente de envío bloquea el inicio de otra. El navegador consulta el estado y las muestras parciales del ESP32 durante la captura, y muestra una captura nueva solo cuando la API ECG confirma que fue guardada. La verificación de conectividad por sí sola no indica que exista una captura.

El servidor HTTP del ESP32 habilita CORS para permitir al navegador consultar `/api/ecg` y enviar formularios URL-encoded a `/configurar` y `/iniciar` desde el origen del tótem. El firmware usa HTTP local sin TLS ni autenticación: mantené ESP32 y FastAPI en una red confiable y no publiques estos servicios en Internet.

## Comunicación ESP32 → FastAPI

Al completar 2500 muestras, el ESP32 descubre FastAPI por mDNS y envía un HTTP POST al puerto anunciado:

```
http://<DIRECCION_DESCUBIERTA>:<PUERTO_ANUNCIADO>/api/v1/ecg/resultados
```

Contrato transmitido:

```json
{
  "episodio_id": 42,
  "dispositivo_id": 7,
  "origen": "SENSOR",
  "data": {
    "frecuencia_muestreo_hz": 250,
    "muestras": [2048, 2051, 2047],
    "unidad": "ADC",
    "adquisicion_id": "UUID-v4-unico-por-captura"
  }
}
```

El ejemplo abreviado no constituye una captura válida: `muestras` debe contener exactamente 2500 valores enteros ADC entre 0 y 4095. `dispositivo_id` es el identificador numérico del registro ECG de código canónico `ECG-001` y se configura en el ESP32 desde el frontend del tótem. En la base de datos inspeccionada ese ID es `1`; el firmware no presupone ni codifica ese número. `adquisicion_id` se crea una sola vez por captura y se conserva en los reintentos. El endpoint original `/api/v1/ecg/resultados` valida episodio, dispositivo, frecuencia, unidad, longitud, valores y UUID antes de guardar. La repetición idéntica es idempotente; un UUID reutilizado con datos distintos se rechaza.

La API guarda cada captura completa al recibirla, conserva el historial y responde HTTP 201 o 200. Ante desconexión o respuesta HTTP de error, el ESP32 conserva la captura en RAM y reintenta con el mismo UUID cada 5 s; no inicia otra captura hasta confirmar el guardado. Un reinicio o pérdida de alimentación mientras espera el reintento sí puede perder esa captura pendiente.

La consulta histórica continúa disponible mediante:

```
GET /api/v1/ecg/resultados/{episodio_id}
```

La pantalla del tótem puede detectar nuevas capturas consultando ese endpoint. El simulador solo se invoca cuando se selecciona explícitamente el modo SIMULACIÓN.

## Señal y procesamiento

Se envían los valores crudos del ADC (0–4095), en orden de adquisición. No hay conversión a milivoltios, filtrado digital, interpolación ni sustitución de muestras en la captura transmitida. Las entradas LO+/LO- detienen y abortan una captura incompleta si detectan electrodos desconectados. No se calculan intervalos ni se identifican ondas P, QRS o T.

La página local del ESP32 conserva una estimación experimental de frecuencia cardiaca, separada de las muestras transmitidas y no guardada con el resultado. Para esa estimación se resta una línea base IIR (`base[n] = 0,995 × base[n−1] + 0,005 × ADC[n]`), se actualiza una envolvente de amplitud con el mismo coeficiente y se buscan picos por encima de `max(80 cuentas ADC, 3 × envolvente)`. Solo se consideran intervalos entre 300 y 2000 ms y se suaviza el resultado con una media ponderada 3:1. Es un indicador técnico no validado, no una medición clínica; el procesamiento no modifica la señal ADC original ni se usa para marcar ondas o diagnosticar.

## Limitaciones y pruebas físicas

- HTTP se debe utilizar únicamente en una red local confiable; no se configura TLS ni autenticación en este firmware.
- La red debe permitir que tótem y ESP32 intercambien mDNS/DNS-SD y HTTP. VLAN separadas, aislamiento de clientes Wi-Fi o reglas de firewall pueden impedir el descubrimiento aunque ambos dispositivos tengan Wi-Fi.
- FastAPI debe escuchar en una interfaz de red (`--host 0.0.0.0`) y el puerto anunciado por `ECG_API_PORT` debe coincidir con el puerto real de Uvicorn.
- La clave Wi-Fi solo se configura en el archivo local ignorado `include/ecg_config.h`; el repositorio no incluye credenciales.
- La frecuencia es una frecuencia objetivo nominal; su precisión, los electrodos y los valores ADC deben verificarse con el hardware real.
- Las pruebas automatizadas de FastAPI no verifican la placa, el AD8232, el Wi-Fi ni la comunicación física.
- Antes de uso se debe probar continuidad de muestras, estado de electrodos, caída/reconexión de Wi-Fi, reintento idempotente y asociación al episodio real.
- Esta integración es experimental y no realiza diagnóstico ni interpretación clínica.
