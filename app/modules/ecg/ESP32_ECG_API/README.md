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
2. Configurá el SSID, la clave Wi-Fi y la URL base HTTP de la API. `ecg_config.h` está excluido de Git.
3. Compilá y cargá desde esta carpeta con PlatformIO (`pio run`, luego `pio run -t upload`).
4. Abrí el monitor serie a 115200 baudios y consultá la IP que recibe el ESP32.
5. Abrí el módulo ECG en el tótem, ingresá la dirección local `http://<IP_DEL_ESP32>` y elegí **Iniciar ECG**. El frontend configura el episodio validado en el ESP32, espera que los electrodos estén conectados y comienza la captura.

El episodio se configura explícitamente desde el frontend del tótem y no queda guardado al reiniciar el ESP32. Una captura pendiente de envío bloquea el inicio de otra. El navegador consulta el estado y las muestras parciales del ESP32 durante la captura, y muestra el resultado solo cuando la API ECG confirma que fue guardado.

El servidor HTTP del ESP32 habilita CORS únicamente para el origen derivado de `ECG_API_BASE_URL`, para que el frontend del tótem pueda consultar `/api/ecg` y enviar formularios URL-encoded a `/configurar` y `/iniciar`. Abrí la interfaz usando el mismo host y puerto configurados para la API; debe servirse desde una red local que pueda alcanzar al ESP32. La configuración actual usa HTTP local, no TLS.

## Comunicación ESP32 → FastAPI

Al completar 2500 muestras, el ESP32 envía un HTTP POST a:

```
http://<IP_DEL_TOTEM>:8000/api/v1/ecg/resultados
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
- La frecuencia es una frecuencia objetivo nominal; su precisión, los electrodos y los valores ADC deben verificarse con el hardware real.
- Las pruebas automatizadas de FastAPI no verifican la placa, el AD8232, el Wi-Fi ni la comunicación física.
- Antes de uso se debe probar continuidad de muestras, estado de electrodos, caída/reconexión de Wi-Fi, reintento idempotente y asociación al episodio real.
- Esta integración es experimental y no realiza diagnóstico ni interpretación clínica.
