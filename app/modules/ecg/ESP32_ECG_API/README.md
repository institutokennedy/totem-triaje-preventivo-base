# ESP32 ECG API

Firmware PlatformIO para ESP32 con sensor AD8232. Envía muestras ADC originales al adaptador FastAPI del módulo ECG. No aplica filtros ni genera muestras para completar capturas.

## Configuración observada en el código

- Plataforma PlatformIO: `esp32dev`, definición genérica de una placa ESP32; no identifica el modelo ni la revisión física.
- Entrada analógica AD8232 OUT: GPIO 34 (ADC1_CH6), resolución configurada en 12 bits y atenuación `ADC_11db`.
- Lead-off LO+: GPIO 26.
- Lead-off LO-: GPIO 27.
- Frecuencia objetivo: 250 Hz (periodo nominal de 4 ms).
- Captura: 10 s, exactamente 2500 muestras.
- Muestra original: cuenta ADC entera, rango 0–4095; se conserva en `muestras`.
- Conversión adicional del firmware: `muestras_mV_OUT` conserva las tensiones calculadas para la salida del AD8232 cuando se inicializa la calibración eFuse.
- Dispositivo del catálogo: código canónico `ECG-001` (ID numérico `1` en la base inspeccionada).

La conexión física y el cableado deben validarse con la placa y el módulo reales antes de uso.

## Conversión a mV_OUT

El ESP32-D0WD-V3, revisión 3.1, fue identificado por serie y su eFuse `ADC_VREF` fue leído como 1093 mV (valor raw 17). En el arranque, el firmware comprueba que ESP-IDF detecte calibración por eFuse Vref, lee el campo y verifica ese valor. Luego crea el calibrador line-fitting para ADC1, GPIO34/ADC1_CH6, 12 bits y `ADC_ATTEN_DB_12` (equivalente a `ADC_11db` en esta configuración).

Cada `analogRead(GPIO34)` produce el raw que se conserva en `muestras`; ese mismo número se pasa a `adc_cali_raw_to_voltage()` para obtener el elemento alineado de `muestras_mV_OUT`. No se efectúa una segunda conversión ADC. El objeto `calibracion_adc` informa estado, método, fuente eFuse, Vref, configuración ADC, chip, revisión y ESP-IDF. Si falla la detección, creación o una conversión, se informa el código y motivo, se conserva ADC y se omite por completo la lista mV_OUT.

La API no autentica al ESP32 ni puede demostrar que una solicitud provenga de ese firmware. Por eso trata toda lista `muestras_mV_OUT` y sus metadatos recibidos por POST como `NO_CONFIABLE`, incluso si declaran calibración correcta; cuando no hay lista, informa `NO_EVALUABLE`. No se implementó autenticación criptográfica. El GET histórico aplica esa clasificación al responder sin modificar los registros guardados. La interfaz del tótem presenta la señal ADC y no grafica los mV_OUT mientras no exista una procedencia verificable.

La conversión del firmware pretende representar la tensión del pin OUT respecto de la referencia de tierra del circuito (`mV_OUT`). No es `mV_ECG`: la ganancia efectiva, offset y respuesta en frecuencia del módulo AD8232 no están caracterizados, por lo que no se convierte la señal diferencial de entrada en mV. La función de calibración ADC tampoco demuestra exactitud metrológica ni autenticidad de origen; hace falta verificar en banco el error, rango útil, offset, repetibilidad y saturación frente a una referencia de tensión trazable. No realizar pruebas con electrodos en personas.

Las capturas históricas continúan almacenando ADC y no se convierten retrospectivamente. La evaluación preventiva sigue usando la unidad ADC y `mV_OUT` no modifica reglas clínicas ni el semáforo.

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
    "muestras_mV_OUT": ["valores mV_OUT calculados por el firmware"],
    "calibracion_adc": {
      "estado": "CALIBRADA",
      "metodo": "ESP_IDF_LINE_FITTING",
      "fuente": "EFUSE_VREF",
      "vref_efuse_raw": 17,
      "vref_efuse_mv": 1093,
      "adc_unit": "ADC1",
      "gpio": 34,
      "canal": 6,
      "resolucion_bits": 12,
      "atenuacion": "ADC_11db/ADC_ATTEN_DB_12",
      "chip_model": "ESP32-D0WD-V3",
      "chip_revision": 301,
      "esp_idf_version": "v5.5.5",
      "error_codigo": null,
      "error": null
    },
    "adquisicion_id": "UUID-v4-unico-por-captura"
  }
}
```

El ejemplo abreviado es esquemático y no constituye una captura válida: `muestras` debe contener exactamente 2500 valores enteros ADC entre 0 y 4095 y, cuando el firmware logra convertir cada muestra, `muestras_mV_OUT` contiene 2500 enteros alineados con esos raw. La cadena mostrada en el ejemplo representa esa lista, no una medición. Si la calibración falla, el firmware envía el estado y error pero omite `muestras_mV_OUT`. `dispositivo_id` es el identificador numérico del registro ECG de código canónico `ECG-001` y se configura en el ESP32 desde el frontend del tótem. En la base de datos inspeccionada ese ID es `1`; el firmware no presupone ni codifica ese número. `adquisicion_id` se crea una sola vez por captura y se conserva en los reintentos. El endpoint `/api/v1/ecg/resultados` valida episodio, dispositivo, frecuencia, unidad, longitud y valores, pero no autentica al cliente; degrada a `NO_CONFIABLE` las listas mV_OUT y metadatos declarados. La repetición idéntica es idempotente; un UUID reutilizado con datos diferentes se rechaza.

La API guarda cada captura completa al recibirla, conserva el historial y responde HTTP 201 o 200. Ante desconexión o respuesta HTTP de error, el ESP32 conserva la captura en RAM y reintenta con el mismo UUID cada 5 s; no inicia otra captura hasta confirmar el guardado. Un reinicio o pérdida de alimentación mientras espera el reintento sí puede perder esa captura pendiente.

La consulta histórica continúa disponible mediante:

```
GET /api/v1/ecg/resultados/{episodio_id}
```

La pantalla del tótem puede detectar nuevas capturas consultando ese endpoint. El simulador solo se invoca cuando se selecciona explícitamente el modo SIMULACIÓN.

## Señal y procesamiento

Se envían los valores crudos del ADC (0–4095), en orden de adquisición, y, si todas las conversiones se completaron, una lista mV_OUT alineada por índice que la API etiqueta `NO_CONFIABLE` por falta de autenticación de origen. No hay filtrado digital, interpolación ni sustitución de muestras en la captura transmitida. Las entradas LO+/LO- detienen y abortan una captura incompleta si detectan electrodos desconectados. No se calculan intervalos ni se identifican ondas P, QRS o T.

La página local del ESP32 conserva una estimación experimental de frecuencia cardiaca, separada de las muestras transmitidas y no guardada con el resultado. Para esa estimación se resta una línea base IIR (`base[n] = 0,995 × base[n−1] + 0,005 × ADC[n]`), se actualiza una envolvente de amplitud con el mismo coeficiente y se buscan picos por encima de `max(80 cuentas ADC, 3 × envolvente)`. Solo se consideran intervalos entre 300 y 2000 ms y se suaviza el resultado con una media ponderada 3:1. Es un indicador técnico no validado, no una medición clínica; el procesamiento no modifica la señal ADC original ni se usa para marcar ondas o diagnosticar.

## Limitaciones y pruebas físicas

- HTTP se debe utilizar únicamente en una red local confiable; no se configura TLS ni autenticación en este firmware.
- La red debe permitir que tótem y ESP32 intercambien mDNS/DNS-SD y HTTP. VLAN separadas, aislamiento de clientes Wi-Fi o reglas de firewall pueden impedir el descubrimiento aunque ambos dispositivos tengan Wi-Fi.
- FastAPI debe escuchar en una interfaz de red (`--host 0.0.0.0`) y el puerto anunciado por `ECG_API_PORT` debe coincidir con el puerto real de Uvicorn.
- La clave Wi-Fi solo se configura en el archivo local ignorado `include/ecg_config.h`; el repositorio no incluye credenciales.
- La frecuencia es una frecuencia objetivo nominal; su precisión, los electrodos y los valores ADC deben verificarse con el hardware real.
- La calibración line-fitting con eFuse Vref fue confirmada por software y se compila, pero la exactitud de mV_OUT requiere validación de banco con fuente e instrumento de referencia.
- Las pruebas automatizadas de FastAPI no verifican la placa, el AD8232, el Wi-Fi ni la comunicación física.
- Antes de uso se debe probar continuidad de muestras, estado de electrodos, caída/reconexión de Wi-Fi, reintento idempotente y asociación al episodio real.
- Esta integración es experimental y no realiza diagnóstico ni interpretación clínica.
