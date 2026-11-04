#include <Arduino.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_adc/adc_cali.h>
#include <esp_adc/adc_cali_scheme.h>
#include <esp_chip_info.h>
#include <esp_efuse.h>
#include <esp_efuse_table.h>
#include <esp_err.h>
#include <esp_idf_version.h>
#include <esp_system.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#if __has_include("ecg_config.h")
#include "ecg_config.h"
#else
#define ECG_WIFI_SSID ""
#define ECG_WIFI_PASSWORD ""
#endif

namespace {

constexpr int ECG_PIN = 34;
constexpr int LO_PLUS_PIN = 26;
constexpr int LO_MINUS_PIN = 27;
constexpr int FRECUENCIA_MUESTREO_HZ = 250;
constexpr int PERIODO_MUESTREO_MS = 1000 / FRECUENCIA_MUESTREO_HZ;
constexpr size_t MUESTRAS_POR_CAPTURA = FRECUENCIA_MUESTREO_HZ * 10;
constexpr unsigned long REINTENTO_ENVIO_MS = 5000;
constexpr unsigned long TIMEOUT_HTTP_MS = 8000;
constexpr unsigned long TIMEOUT_CONEXION_WIFI_MS = 15000;
constexpr unsigned long INTERVALO_REINTENTO_WIFI_MS = 15000;
constexpr unsigned long INTERVALO_REINTENTO_MDNS_MS = 5000;
constexpr uint32_t ADC_VREF_EFUSE_RAW_VERIFICADO = 17;
constexpr uint32_t ADC_VREF_EFUSE_MV_VERIFICADO = 1093;

WebServer server(80);
portMUX_TYPE capturaMux = portMUX_INITIALIZER_UNLOCKED;
uint16_t muestras[MUESTRAS_POR_CAPTURA] = {};
uint16_t muestrasCopia[MUESTRAS_POR_CAPTURA] = {};
int muestrasMvOut[MUESTRAS_POR_CAPTURA] = {};
int muestrasMvOutCopia[MUESTRAS_POR_CAPTURA] = {};
adc_cali_handle_t calibradorAdc = nullptr;
volatile size_t cantidadMuestras = 0;
volatile size_t cantidadMuestrasMvOut = 0;
volatile bool adquisicionEnCurso = false;
volatile bool capturaLista = false;
volatile bool capturaAbortada = false;
volatile bool electrodosConectados = false;
volatile bool calibracionAdcDisponible = false;
volatile bool calibracionCapturaValida = false;
volatile int calibracionAdcErrorCodigo = ESP_ERR_INVALID_STATE;
volatile uint16_t ultimaMuestraADC = 0;
volatile int bpmEstimadoExperimental = 0;
adc_cali_line_fitting_efuse_val_t fuenteCalibracionAdc =
    ADC_CALI_LINE_FITTING_EFUSE_VAL_DEFAULT_VREF;
uint32_t adcVrefEfuseRaw = 0;
uint32_t adcVrefEfuseMv = 0;
const char* calibracionAdcError = "Calibrador ADC no inicializado.";

struct EstadoCalibracionAdcSnapshot {
  bool disponible;
  int codigoError;
  const char* detalleError;
};

int episodioId = 0;
int dispositivoId = 0;
bool configuracionWifiValida = false;
bool servidorHttpIniciado = false;
bool mdnsIniciado = false;
bool wifiEstabaConectado = false;
bool reintentoWifiPendiente = false;
String apiHost;
uint16_t apiPort = 0;
unsigned long ultimoIntentoWifi = 0;
unsigned long inicioReintentoWifi = 0;
unsigned long ultimoIntentoMdns = 0;
unsigned long ultimoDescubrimientoApi = 0;
String adquisicionId;
String ultimoMensaje = "Configure Wi-Fi y el episodio antes de iniciar.";
unsigned long ultimoIntentoEnvio = 0;
int ultimoCodigoHttp = 0;
bool direccionIpMostrada = false;
float lineaBaseExperimental = 2048.0f;
float amplitudMediaExperimental = 50.0f;
bool detectandoPicoExperimental = false;
int latidosValidosExperimental = 0;
unsigned long ultimoLatidoExperimental = 0;

const char PAGINA_WEB[] PROGMEM = R"rawliteral(
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ESP32 ECG</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:56rem;margin:2rem auto;padding:0 1rem;color:#172033}
    section{border:1px solid #cbd5e1;border-radius:.7rem;padding:1rem;margin:1rem 0}
    canvas{display:block;width:100%;height:auto;border:1px solid #94a3b8;background:#f8fafc}
    label{display:block;margin:.7rem 0}
    input,button{padding:.55rem;font:inherit}
    button{margin-right:.5rem}
    [role=status]{min-height:1.5em}
  </style>
</head>
<body>
  <h1>Adquisicion ECG AD8232</h1>
  <p>La senal se muestra como muestras ADC originales, sin filtrado.</p>
  <section>
    <h2>Última estimación de frecuencia durante la adquisición (experimental)</h2>
    <p id="bpm">—</p>
    <p>Estimación local no validada para uso clínico; no se transmite ni se guarda con la captura.</p>
  </section>
  <section>
    <h2>Contexto de episodio</h2>
    <p>Ingresá el ID real del episodio que muestra el tótem. Se solicita nuevamente al reiniciar el ESP32.</p>
    <form id="episodio-form">
      <label for="episodio-id">Episodio ID</label>
      <input id="episodio-id" name="episodio_id" type="number" min="1" step="1" required>
      <label for="dispositivo-id">Dispositivo ID (código ECG-001)</label>
      <input id="dispositivo-id" name="dispositivo_id" type="number" min="1" step="1" required>
      <button type="submit">Configurar episodio</button>
    </form>
    <p id="estado" role="status">Conectando con el dispositivo…</p>
    <p id="conectividad"></p>
    <button id="iniciar" type="button" disabled>Iniciar captura de 10 s</button>
    <button id="detener" type="button" disabled>Cancelar captura incompleta</button>
  </section>
  <section>
    <h2>Muestras adquiridas</h2>
    <p id="detalle">Sin muestras recibidas.</p>
    <canvas id="grafico" width="900" height="320" aria-label="Muestras ADC reales"></canvas>
  </section>
  <script>
    const form=document.getElementById("episodio-form");
    const state=document.getElementById("estado");
    const connectivity=document.getElementById("conectividad");
    const start=document.getElementById("iniciar");
    const stop=document.getElementById("detener");
    const detail=document.getElementById("detalle");
    const bpm=document.getElementById("bpm");
    const canvas=document.getElementById("grafico");
    const ctx=canvas.getContext("2d");
    let episodioConfigurado=false;

    form.addEventListener("submit",async(event)=>{
      event.preventDefault();
      const body=new URLSearchParams(new FormData(form));
      try{
        const response=await fetch("/configurar",{method:"POST",body});
        const result=await response.json();
        if(!response.ok)throw new Error(result.detail||`HTTP ${response.status}`);
        episodioConfigurado=true;
        state.textContent=`Episodio ${result.episodio_id} configurado.`;
        start.disabled=false;
      }catch(error){
        episodioConfigurado=false;
        start.disabled=true;
        state.textContent=`Error de configuración: ${error.message}`;
      }
    });

    start.addEventListener("click",async()=>{
      try{
        const response=await fetch("/iniciar",{method:"POST"});
        const result=await response.json();
        if(!response.ok)throw new Error(result.detail||`HTTP ${response.status}`);
        state.textContent="Adquisición en curso: 250 Hz durante 10 s.";
        start.disabled=true;
        stop.disabled=false;
      }catch(error){state.textContent=`No se pudo iniciar: ${error.message}`;}
    });

    stop.addEventListener("click",async()=>{
      try{
        const response=await fetch("/detener",{method:"POST"});
        const result=await response.json();
        if(!response.ok)throw new Error(result.detail||`HTTP ${response.status}`);
        state.textContent=result.mensaje;
      }catch(error){state.textContent=`No se pudo cancelar: ${error.message}`;}
    });

    function dibujar(muestras){
      ctx.clearRect(0,0,canvas.width,canvas.height);
      if(!muestras.length)return;
      const minimo=Math.min(...muestras);
      const maximo=Math.max(...muestras);
      const rango=maximo-minimo||1;
      ctx.strokeStyle="#cbd5e1";
      ctx.lineWidth=1;
      for(let y=0;y<=4;y++){
        const posicion=y*canvas.height/4;
        ctx.beginPath();ctx.moveTo(0,posicion);ctx.lineTo(canvas.width,posicion);ctx.stroke();
      }
      ctx.fillStyle="#334155";
      ctx.fillText(String(maximo),4,12);
      ctx.fillText(String(minimo),4,canvas.height-4);
      ctx.strokeStyle="#15803d";
      ctx.lineWidth=1.5;
      ctx.beginPath();
      muestras.forEach((valor,index)=>{
        const x=index*canvas.width/Math.max(muestras.length-1,1);
        const y=canvas.height-(valor-minimo)*canvas.height/rango;
        if(index===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      });
      ctx.stroke();
    }

    async function actualizar(){
      try{
        const response=await fetch("/api/ecg",{cache:"no-store"});
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        const data=await response.json();
        if(data.episodio_id){
          document.getElementById("episodio-id").value=data.episodio_id;
          document.getElementById("dispositivo-id").value=data.dispositivo_id;
          episodioConfigurado=true;
        }
        start.disabled=!episodioConfigurado||data.captura_pendiente||data.adquisicion_en_curso;
        stop.disabled=!data.adquisicion_en_curso;
        state.textContent=data.mensaje;
        connectivity.textContent=`Wi-Fi: ${data.wifi_conectado?"conectado":"desconectado"} · Electrodos: ${data.electrodos_conectados?"conectados":"desconectados"}`;
        bpm.textContent=data.bpm>0?`${data.bpm} lpm (experimental)`:"—";
        detail.textContent=`${data.muestras.length} muestras · ${data.frecuencia_muestreo_hz} Hz · ADC · ${data.adquisicion_id||"sin adquisición activa"}`;
        dibujar(data.muestras);
      }catch(error){
        state.textContent=`Error de comunicación con el ESP32: ${error.message}`;
      }finally{setTimeout(actualizar,1000);}
    }
    actualizar();
  </script>
</body>
</html>
)rawliteral";

String crearUUID() {
  uint8_t bytes[16];
  esp_fill_random(bytes, sizeof(bytes));
  bytes[6] = static_cast<uint8_t>((bytes[6] & 0x0F) | 0x40);
  bytes[8] = static_cast<uint8_t>((bytes[8] & 0x3F) | 0x80);
  char uuid[37];
  snprintf(
      uuid,
      sizeof(uuid),
      "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6],
      bytes[7], bytes[8], bytes[9], bytes[10], bytes[11], bytes[12], bytes[13],
      bytes[14], bytes[15]);
  return String(uuid);
}

String escaparJson(const String& valor) {
  String salida;
  salida.reserve(valor.length() + 8);
  for (size_t indice = 0; indice < valor.length(); ++indice) {
    const char caracter = valor[indice];
    if (caracter == '"' || caracter == '\\') {
      salida += '\\';
      salida += caracter;
    } else if (static_cast<uint8_t>(caracter) < 0x20) {
      salida += ' ';
    } else {
      salida += caracter;
    }
  }
  return salida;
}

void marcarErrorCalibracionAdc(esp_err_t error, const char* detalle) {
  portENTER_CRITICAL(&capturaMux);
  calibracionAdcDisponible = false;
  calibracionCapturaValida = false;
  calibracionAdcErrorCodigo = error;
  calibracionAdcError = detalle;
  portEXIT_CRITICAL(&capturaMux);
  Serial.printf(
      "Error de calibración ADC: %s (%d): %s\n",
      esp_err_to_name(error),
      static_cast<int>(error),
      detalle);
}

void inicializarCalibracionAdc() {
  adc_cali_line_fitting_efuse_val_t fuente =
      ADC_CALI_LINE_FITTING_EFUSE_VAL_DEFAULT_VREF;
  esp_err_t resultado = adc_cali_scheme_line_fitting_check_efuse(&fuente);
  if (resultado != ESP_OK) {
    marcarErrorCalibracionAdc(
        resultado,
        "No se pudo detectar el esquema de calibración ADC eFuse.");
    return;
  }

  fuenteCalibracionAdc = fuente;
  if (fuente != ADC_CALI_LINE_FITTING_EFUSE_VAL_EFUSE_VREF) {
    marcarErrorCalibracionAdc(
        ESP_ERR_NOT_SUPPORTED,
        "La fuente eFuse detectada no es ADC_VREF verificada.");
    return;
  }

  resultado = esp_efuse_read_field_blob(
      ESP_EFUSE_ADC_VREF,
      &adcVrefEfuseRaw,
      5);
  if (resultado != ESP_OK) {
    marcarErrorCalibracionAdc(
        resultado,
        "No se pudo leer el campo ADC_VREF eFuse.");
    return;
  }
  if (adcVrefEfuseRaw != ADC_VREF_EFUSE_RAW_VERIFICADO) {
    marcarErrorCalibracionAdc(
        ESP_ERR_INVALID_STATE,
        "El valor ADC_VREF eFuse no coincide con el verificado (1093 mV).");
    return;
  }
  adcVrefEfuseMv = ADC_VREF_EFUSE_MV_VERIFICADO;

  const adc_cali_line_fitting_config_t configuracion = {
      .unit_id = ADC_UNIT_1,
      .atten = ADC_ATTEN_DB_12,
      .bitwidth = ADC_BITWIDTH_12,
      .default_vref = 0,
  };
  resultado = adc_cali_create_scheme_line_fitting(
      &configuracion,
      &calibradorAdc);
  if (resultado != ESP_OK) {
    marcarErrorCalibracionAdc(
        resultado,
        "No se pudo crear el calibrador ADC line-fitting.");
    return;
  }

  portENTER_CRITICAL(&capturaMux);
  calibracionAdcErrorCodigo = ESP_OK;
  calibracionAdcError = "";
  calibracionAdcDisponible = true;
  portEXIT_CRITICAL(&capturaMux);
  Serial.printf(
      "Calibrador ADC listo: ADC1 GPIO34, 12 bits, ADC_11db/ADC_ATTEN_DB_12, "
      "eFuse Vref=%u mV.\n",
      static_cast<unsigned int>(adcVrefEfuseMv));
}

String metadatosCalibracionAdcJson(
    const EstadoCalibracionAdcSnapshot& estado) {
  esp_chip_info_t chip = {};
  esp_chip_info(&chip);
  String json = "{\"estado\":\"";
  json += estado.disponible ? "CALIBRADA" : "ERROR";
  json += "\",\"metodo\":\"ESP_IDF_LINE_FITTING\",\"fuente\":\"";
  if (fuenteCalibracionAdc ==
      ADC_CALI_LINE_FITTING_EFUSE_VAL_EFUSE_VREF) {
    json += "EFUSE_VREF";
  } else if (fuenteCalibracionAdc ==
             ADC_CALI_LINE_FITTING_EFUSE_VAL_EFUSE_TP) {
    json += "EFUSE_TWO_POINT";
  } else {
    json += "NO_DISPONIBLE";
  }
  json += "\",\"vref_efuse_raw\":";
  json += String(adcVrefEfuseRaw);
  json += ",\"vref_efuse_mv\":";
  json += adcVrefEfuseMv > 0 ? String(adcVrefEfuseMv) : String("null");
  json += ",\"adc_unit\":\"ADC1\",\"gpio\":34,\"canal\":6,"
          "\"resolucion_bits\":12,"
          "\"atenuacion\":\"ADC_11db/ADC_ATTEN_DB_12\","
          "\"chip_model\":\"";
  json += escaparJson(String(ESP.getChipModel()));
  json += "\",\"chip_revision\":";
  json += String(chip.revision);
  json += ",\"esp_idf_version\":\"";
  json += escaparJson(String(esp_get_idf_version()));
  json += "\",\"error_codigo\":";
  json += estado.disponible ? String("null") : String(estado.codigoError);
  json += ",\"error\":\"";
  json += estado.disponible
              ? String("")
              : escaparJson(String(estado.detalleError));
  json += "\"}";
  return json;
}

void aplicarCabecerasCors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Accept, Content-Type");
  server.sendHeader("Access-Control-Allow-Private-Network", "true");
}

void responderPreflight() {
  aplicarCabecerasCors();
  server.send(204, "text/plain", "");
}

void reiniciarEstimacionExperimental() {
  bpmEstimadoExperimental = 0;
  lineaBaseExperimental = 2048.0f;
  amplitudMediaExperimental = 50.0f;
  detectandoPicoExperimental = false;
  latidosValidosExperimental = 0;
  ultimoLatidoExperimental = 0;
}

void actualizarEstimacionExperimental(uint16_t lecturaADC) {
  lineaBaseExperimental =
      0.995f * lineaBaseExperimental + 0.005f * lecturaADC;
  const float senalDerivada =
      static_cast<float>(lecturaADC) - lineaBaseExperimental;
  amplitudMediaExperimental =
      0.995f * amplitudMediaExperimental + 0.005f * fabsf(senalDerivada);
  const float umbral =
      amplitudMediaExperimental * 3.0f > 80.0f
          ? amplitudMediaExperimental * 3.0f
          : 80.0f;
  const unsigned long ahora = millis();

  if (senalDerivada > umbral && !detectandoPicoExperimental) {
    detectandoPicoExperimental = true;
    const unsigned long intervalo = ahora - ultimoLatidoExperimental;
    if (ultimoLatidoExperimental > 0 && intervalo >= 300 && intervalo <= 2000) {
      const int nuevoBPM = static_cast<int>(60000 / intervalo);
      bpmEstimadoExperimental =
          latidosValidosExperimental == 0
              ? nuevoBPM
              : (bpmEstimadoExperimental * 3 + nuevoBPM) / 4;
      ++latidosValidosExperimental;
    }
    if (ultimoLatidoExperimental == 0 || intervalo >= 300) {
      ultimoLatidoExperimental = ahora;
    }
  }

  if (senalDerivada < umbral * 0.4f) {
    detectandoPicoExperimental = false;
  }
  if (ultimoLatidoExperimental > 0 && ahora - ultimoLatidoExperimental > 3000) {
    bpmEstimadoExperimental = 0;
    latidosValidosExperimental = 0;
    ultimoLatidoExperimental = 0;
  }
}

void responderError(int status, const String& detail) {
  String body = "{\"detail\":\"" + escaparJson(detail) + "\"}";
  aplicarCabecerasCors();
  server.send(status, "application/json", body);
}

void configurarEpisodio() {
  if (adquisicionEnCurso || capturaLista) {
    responderError(409, "No se puede cambiar el episodio durante una captura.");
    return;
  }

  const String valor = server.arg("episodio_id");
  const String valorDispositivo = server.arg("dispositivo_id");
  char* finEpisodio = nullptr;
  char* finDispositivo = nullptr;
  const long parsedEpisodio = strtol(valor.c_str(), &finEpisodio, 10);
  const long parsedDispositivo =
      strtol(valorDispositivo.c_str(), &finDispositivo, 10);
  if (valor.isEmpty() || finEpisodio == valor.c_str() ||
      *finEpisodio != '\0' || parsedEpisodio <= 0 ||
      parsedEpisodio > INT32_MAX || valorDispositivo.isEmpty() ||
      finDispositivo == valorDispositivo.c_str() || *finDispositivo != '\0' ||
      parsedDispositivo <= 0 || parsedDispositivo > INT32_MAX) {
    responderError(
        422,
        "episodio_id y dispositivo_id deben ser enteros positivos.");
    return;
  }

  episodioId = static_cast<int>(parsedEpisodio);
  dispositivoId = static_cast<int>(parsedDispositivo);
  capturaAbortada = false;
  adquisicionId = "";
  ultimoMensaje = "Episodio " + String(episodioId) +
                  " y dispositivo " + String(dispositivoId) + " configurados.";
  aplicarCabecerasCors();
  server.send(
      200,
      "application/json",
      "{\"mensaje\":\"Episodio y dispositivo configurados\",\"episodio_id\":" +
          String(episodioId) + ",\"dispositivo_id\":" +
          String(dispositivoId) + "}");
}

void iniciarAdquisicion() {
  if (!configuracionWifiValida) {
    responderError(503, "Configure Wi-Fi en include/ecg_config.h.");
    return;
  }
  if (WiFi.status() != WL_CONNECTED || !mdnsIniciado) {
    responderError(503, "El ESP32 no está conectado al Wi-Fi.");
    return;
  }
  if (apiHost.isEmpty() || apiPort == 0) {
    responderError(503, "No se encontró el servicio FastAPI mediante mDNS.");
    return;
  }
  if (episodioId <= 0) {
    responderError(409, "Configure el episodio activo antes de iniciar.");
    return;
  }
  if (adquisicionEnCurso || capturaLista) {
    responderError(409, "Hay una adquisición en curso o pendiente de envío.");
    return;
  }

  const String nuevoId = crearUUID();
  adquisicionId = nuevoId;
  portENTER_CRITICAL(&capturaMux);
  cantidadMuestras = 0;
  cantidadMuestrasMvOut = 0;
  capturaAbortada = false;
  capturaLista = false;
  calibracionCapturaValida = calibracionAdcDisponible;
  adquisicionEnCurso = true;
  portEXIT_CRITICAL(&capturaMux);

  ultimoCodigoHttp = 0;
  ultimoMensaje = "Adquisición en curso: 250 Hz durante 10 s.";
  aplicarCabecerasCors();
  server.send(
      202,
      "application/json",
      "{\"mensaje\":\"Adquisición iniciada\",\"adquisicion_id\":\"" +
          adquisicionId + "\"}");
}

void detenerAdquisicion() {
  portENTER_CRITICAL(&capturaMux);
  const bool estabaEnCurso = adquisicionEnCurso;
  if (estabaEnCurso) {
    adquisicionEnCurso = false;
    capturaAbortada = true;
    cantidadMuestras = 0;
  }
  portEXIT_CRITICAL(&capturaMux);

  if (!estabaEnCurso) {
    responderError(409, "No hay una adquisición incompleta para cancelar.");
    return;
  }
  adquisicionId = "";
  ultimoMensaje = "Captura incompleta cancelada; no se envió ni se completó con datos ficticios.";
  aplicarCabecerasCors();
  server.send(
      200,
      "application/json",
      "{\"mensaje\":\"Captura incompleta cancelada sin enviar muestras\"}");
}

void tareaAdquisicion(void*) {
  TickType_t proximoDespertar = xTaskGetTickCount();
  const TickType_t periodo = pdMS_TO_TICKS(PERIODO_MUESTREO_MS);

  for (;;) {
    vTaskDelayUntil(&proximoDespertar, periodo);
    const bool electrodosDesconectados =
        digitalRead(LO_PLUS_PIN) == HIGH || digitalRead(LO_MINUS_PIN) == HIGH;
    if (electrodosDesconectados) {
      portENTER_CRITICAL(&capturaMux);
      electrodosConectados = false;
      if (adquisicionEnCurso) {
        adquisicionEnCurso = false;
        capturaAbortada = true;
        cantidadMuestras = 0;
      }
      reiniciarEstimacionExperimental();
      portEXIT_CRITICAL(&capturaMux);
      continue;
    }

    portENTER_CRITICAL(&capturaMux);
    electrodosConectados = true;
    portEXIT_CRITICAL(&capturaMux);
    if (!adquisicionEnCurso) {
      continue;
    }

    const uint16_t muestra = static_cast<uint16_t>(analogRead(ECG_PIN));
    int muestraMvOut = 0;
    esp_err_t resultadoConversion = ESP_ERR_INVALID_STATE;
    if (calibradorAdc != nullptr && calibracionAdcDisponible) {
      resultadoConversion = adc_cali_raw_to_voltage(
          calibradorAdc,
          static_cast<int>(muestra),
          &muestraMvOut);
      if (resultadoConversion != ESP_OK) {
        marcarErrorCalibracionAdc(
            resultadoConversion,
            "Falló la conversión de una muestra ADC a mV_OUT.");
      }
    }
    actualizarEstimacionExperimental(muestra);
    portENTER_CRITICAL(&capturaMux);
    ultimaMuestraADC = muestra;
    if (adquisicionEnCurso && cantidadMuestras < MUESTRAS_POR_CAPTURA) {
      const size_t indice = cantidadMuestras;
      muestras[indice] = muestra;
      cantidadMuestras = cantidadMuestras + 1;
      if (calibracionCapturaValida && resultadoConversion == ESP_OK) {
        muestrasMvOut[indice] = muestraMvOut;
        cantidadMuestrasMvOut = cantidadMuestrasMvOut + 1;
      }
      if (cantidadMuestras == MUESTRAS_POR_CAPTURA) {
        adquisicionEnCurso = false;
        capturaLista = true;
      }
    }
    portEXIT_CRITICAL(&capturaMux);
  }
}

bool enviarCaptura() {
  if (WiFi.status() != WL_CONNECTED) {
    ultimoCodigoHttp = 0;
    ultimoMensaje = "Error de comunicación: Wi-Fi desconectado; se conserva la captura para reintentar.";
    return false;
  }
  if (apiHost.isEmpty() || apiPort == 0) {
    ultimoCodigoHttp = 0;
    ultimoMensaje = "Error de comunicación: FastAPI no está disponible mediante mDNS.";
    return false;
  }

  size_t cantidad = 0;
  size_t cantidadMvOut = 0;
  int episodio = 0;
  bool calibracionValida = false;
  EstadoCalibracionAdcSnapshot estadoCalibracion = {};
  portENTER_CRITICAL(&capturaMux);
  cantidad = cantidadMuestras;
  cantidadMvOut = cantidadMuestrasMvOut;
  calibracionValida = calibracionCapturaValida;
  estadoCalibracion.disponible = calibracionAdcDisponible;
  estadoCalibracion.codigoError = calibracionAdcErrorCodigo;
  estadoCalibracion.detalleError = calibracionAdcError;
  if (cantidad == MUESTRAS_POR_CAPTURA && capturaLista) {
    memcpy(muestrasCopia, muestras, sizeof(muestrasCopia));
    if (calibracionValida && cantidadMvOut == cantidad) {
      memcpy(muestrasMvOutCopia, muestrasMvOut, sizeof(muestrasMvOutCopia));
    }
  }
  portEXIT_CRITICAL(&capturaMux);
  episodio = episodioId;
  const String id = adquisicionId;

  if (cantidad != MUESTRAS_POR_CAPTURA || id.isEmpty() || episodio <= 0 ||
      dispositivoId <= 0) {
    ultimoMensaje = "Error interno: la captura pendiente no está completa.";
    return false;
  }

  String payload;
  payload.reserve(60000);
  payload = "{\"episodio_id\":";
  payload += String(episodio);
  payload += ",\"dispositivo_id\":";
  payload += String(dispositivoId);
  payload += ",\"origen\":\"SENSOR\",\"data\":{";
  payload += "\"frecuencia_muestreo_hz\":250,\"muestras\":[";
  for (size_t indice = 0; indice < cantidad; ++indice) {
    if (indice > 0) {
      payload += ',';
    }
    payload += String(muestrasCopia[indice]);
  }
  payload += "],\"unidad\":\"ADC\",\"calibracion_adc\":";
  payload += metadatosCalibracionAdcJson(estadoCalibracion);
  if (calibracionValida && cantidadMvOut == cantidad) {
    payload += ",\"muestras_mV_OUT\":[";
    for (size_t indice = 0; indice < cantidadMvOut; ++indice) {
      if (indice > 0) {
        payload += ',';
      }
      payload += String(muestrasMvOutCopia[indice]);
    }
    payload += "]";
    payload += ",\"estado_mV_OUT\":\"NO_CONFIABLE\"";
  } else {
    payload += ",\"estado_mV_OUT\":\"NO_EVALUABLE\"";
  }
  payload += ",\"adquisicion_id\":\"";
  payload += id;
  payload += "\"}}";

  HTTPClient http;
  const String url = "http://" + apiHost + ":" + String(apiPort) +
                     "/api/v1/ecg/resultados";
  http.setTimeout(TIMEOUT_HTTP_MS);
  if (!http.begin(url)) {
    ultimoCodigoHttp = 0;
    ultimoMensaje = "Error de comunicación: no se pudo abrir la conexión HTTP con la API.";
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  ultimoCodigoHttp = http.POST(payload);
  const String respuesta = http.getString();
  http.end();

  if (ultimoCodigoHttp < 200 || ultimoCodigoHttp >= 300) {
    ultimoMensaje = "Error HTTP " + String(ultimoCodigoHttp) +
                    " al guardar la captura; se conserva para reintentar. " +
                    respuesta;
    return false;
  }

  portENTER_CRITICAL(&capturaMux);
  cantidadMuestras = 0;
  capturaLista = false;
  capturaAbortada = false;
  adquisicionId = "";
  portEXIT_CRITICAL(&capturaMux);

  ultimoMensaje = "Captura finalizada y guardada por la API.";
  Serial.println(ultimoMensaje);
  Serial.println(respuesta);
  return true;
}

void apiECG() {
  size_t cantidad = 0;
  bool enCurso = false;
  bool pendiente = false;
  bool abortada = false;
  bool electrodos = false;
  bool calibracionValida = false;
  EstadoCalibracionAdcSnapshot estadoCalibracion = {};
  size_t cantidadMvOut = 0;
  uint16_t ultimaMuestra = 0;
  String id = adquisicionId;
  int bpm = 0;

  portENTER_CRITICAL(&capturaMux);
  cantidad = cantidadMuestras;
  enCurso = adquisicionEnCurso;
  pendiente = capturaLista;
  abortada = capturaAbortada;
  electrodos = electrodosConectados;
  calibracionValida = calibracionCapturaValida;
  cantidadMvOut = cantidadMuestrasMvOut;
  estadoCalibracion.disponible = calibracionAdcDisponible;
  estadoCalibracion.codigoError = calibracionAdcErrorCodigo;
  estadoCalibracion.detalleError = calibracionAdcError;
  ultimaMuestra = ultimaMuestraADC;
  bpm = bpmEstimadoExperimental;
  if (cantidad > 0) {
    memcpy(muestrasCopia, muestras, cantidad * sizeof(uint16_t));
    if (calibracionValida && cantidadMvOut == cantidad) {
      memcpy(muestrasMvOutCopia, muestrasMvOut, cantidad * sizeof(int));
    }
  }
  portEXIT_CRITICAL(&capturaMux);
  if (abortada) {
    id = "";
  }

  String mensaje = ultimoMensaje;
  if (!electrodos && enCurso) {
    mensaje = "Adquisición abortada: electrodos desconectados.";
  } else if (!electrodos) {
    mensaje = "Electrodos desconectados.";
  } else if (abortada) {
    mensaje = "Captura abortada por desconexión de electrodos.";
  } else if (pendiente) {
    if (WiFi.status() != WL_CONNECTED) {
      mensaje = "Wi-Fi desconectado; captura completa conservada para reintentar.";
    } else if (ultimoCodigoHttp != 0 &&
               (ultimoCodigoHttp < 200 || ultimoCodigoHttp >= 300)) {
      mensaje = ultimoMensaje;
    } else {
      mensaje = "Captura completa; enviando o reintentando el envío a la API.";
    }
  } else if (enCurso) {
    mensaje = "Adquisición en curso.";
  } else if (episodioId <= 0) {
    mensaje = "Configure el episodio activo para iniciar una captura.";
  }

  String json;
  json.reserve(256 + cantidad * 14);
  json = "{\"ecg\":";
  json += String(ultimaMuestra);
  json += ",\"bpm\":";
  json += String(bpm);
  json += ",\"electrodos\":\"";
  json += (electrodos ? "conectados" : "desconectados");
  json += "\",\"tiempo_ms\":";
  json += String(millis());
  json += ",\"frecuencia_muestreo_hz\":250,\"unidad\":\"ADC\",\"episodio_id\":";
  json += (episodioId > 0 ? String(episodioId) : String("null"));
  json += ",\"dispositivo_id\":";
  json += (dispositivoId > 0 ? String(dispositivoId) : String("null"));
  json += ",\"adquisicion_id\":\"";
  json += id;
  json += "\",\"adquisicion_en_curso\":";
  json += enCurso ? "true" : "false";
  json += ",\"captura_pendiente\":";
  json += pendiente ? "true" : "false";
  json += ",\"electrodos_conectados\":";
  json += electrodos ? "true" : "false";
  json += ",\"wifi_conectado\":";
  json += (WiFi.status() == WL_CONNECTED ? "true" : "false");
  json += ",\"backend_conectado\":";
  json += (!apiHost.isEmpty() && apiPort > 0 ? "true" : "false");
  json += ",\"muestra_adc\":";
  json += String(ultimaMuestra);
  json += ",\"cantidad_muestras\":";
  json += String(cantidad);
  json += ",\"muestras\":[";
  for (size_t indice = 0; indice < cantidad; ++indice) {
    if (indice > 0) {
      json += ',';
    }
    json += String(muestrasCopia[indice]);
  }
  json += "],\"calibracion_adc\":";
  json += metadatosCalibracionAdcJson(estadoCalibracion);
  if (calibracionValida && cantidadMvOut == cantidad) {
    json += ",\"muestras_mV_OUT\":[";
    for (size_t indice = 0; indice < cantidadMvOut; ++indice) {
      if (indice > 0) {
        json += ',';
      }
      json += String(muestrasMvOutCopia[indice]);
    }
    json += "]";
    json += ",\"estado_mV_OUT\":\"NO_CONFIABLE\"";
  } else {
    json += ",\"estado_mV_OUT\":\"NO_EVALUABLE\"";
  }
  json += ",\"codigo_http\":";
  json += String(ultimoCodigoHttp);
  json += ",\"mensaje\":\"";
  json += escaparJson(mensaje);
  json += "\"}";
  aplicarCabecerasCors();
  server.send(200, "application/json", json);
}

void configurarRutas() {
  if (servidorHttpIniciado || WiFi.status() != WL_CONNECTED) {
    return;
  }

  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html; charset=utf-8", PAGINA_WEB);
  });
  server.on("/api/ecg", HTTP_GET, apiECG);
  server.on("/api/ecg", HTTP_OPTIONS, responderPreflight);
  server.on("/configurar", HTTP_POST, configurarEpisodio);
  server.on("/configurar", HTTP_OPTIONS, responderPreflight);
  server.on("/iniciar", HTTP_POST, iniciarAdquisicion);
  server.on("/iniciar", HTTP_OPTIONS, responderPreflight);
  server.on("/detener", HTTP_POST, detenerAdquisicion);
  server.on("/detener", HTTP_OPTIONS, responderPreflight);
  Serial.println("Iniciando servidor HTTP...");
  server.begin();
  servidorHttpIniciado = true;
  Serial.println("Servidor HTTP iniciado en el puerto 80.");
  Serial.println("Monitor ECG disponible en la dirección IP del ESP32.");
}

void actualizarServiciosMdns() {
  const bool wifiConectado = WiFi.status() == WL_CONNECTED;
  if (!wifiConectado) {
    if (wifiEstabaConectado && mdnsIniciado) {
      MDNS.end();
    }
    wifiEstabaConectado = false;
    mdnsIniciado = false;
    ultimoIntentoMdns = 0;
    apiHost = "";
    apiPort = 0;
    return;
  }

  wifiEstabaConectado = true;
  if (!mdnsIniciado) {
    if (millis() - ultimoIntentoMdns < INTERVALO_REINTENTO_MDNS_MS) {
      return;
    }
    ultimoIntentoMdns = millis();
    mdnsIniciado = MDNS.begin("ecg-001");
    if (!mdnsIniciado) {
      Serial.println("Error: MDNS.begin(\"ecg-001\") no pudo iniciar mDNS.");
      ultimoMensaje = "Error: no se pudo iniciar mDNS en el ESP32.";
      return;
    }

    Serial.println("MDNS.begin(\"ecg-001\"): correcto.");
    if (!MDNS.addService("ecg", "tcp", 80)) {
      Serial.println("Error: no se pudo anunciar _ecg._tcp en el puerto 80.");
      ultimoMensaje = "Error: no se pudo anunciar el servicio ECG por mDNS.";
      MDNS.end();
      mdnsIniciado = false;
      return;
    }
    MDNS.addServiceTxt("ecg", "tcp", "codigo", "ECG-001");
    Serial.println("Servicio _ecg._tcp anunciado en puerto 80 (codigo=ECG-001).");
    ultimoMensaje = "Wi-Fi conectado; buscando FastAPI mediante mDNS.";
  }

  if (millis() - ultimoDescubrimientoApi < 5000) {
    return;
  }
  ultimoDescubrimientoApi = millis();
  const int servicios = MDNS.queryService("totem-api", "tcp");
  for (int indice = 0; indice < servicios; ++indice) {
    const IPAddress direccion = MDNS.address(indice);
    const uint16_t puerto = MDNS.port(indice);
    if (direccion != IPAddress(0, 0, 0, 0) && puerto > 0) {
      apiHost = direccion.toString();
      apiPort = puerto;
      Serial.printf(
          "Búsqueda _totem-api._tcp: FastAPI encontrado en %s:%u.\n",
          apiHost.c_str(),
          static_cast<unsigned int>(apiPort));
      ultimoMensaje = "FastAPI encontrado mediante mDNS.";
      return;
    }
  }
  apiHost = "";
  apiPort = 0;
  Serial.println("Búsqueda _totem-api._tcp: FastAPI no encontrado.");
  ultimoMensaje = "Wi-Fi conectado; FastAPI todavía no fue encontrado mediante mDNS.";
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("=== INICIO ESP32 ECG ===");
  Serial.println("Serial inicializado correctamente");
  Serial.println("Configurando pines...");
  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(ECG_PIN, ADC_11db);
  inicializarCalibracionAdc();

  Serial.println("Configurando Wi-Fi...");
  configuracionWifiValida =
      strlen(ECG_WIFI_SSID) > 0 && strlen(ECG_WIFI_PASSWORD) > 0;
  if (configuracionWifiValida) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    ultimoIntentoWifi = millis();
    WiFi.begin(ECG_WIFI_SSID, ECG_WIFI_PASSWORD);

    const unsigned long inicioConexion = millis();
    while (WiFi.status() != WL_CONNECTED) {
      const unsigned long transcurrido = millis() - inicioConexion;
      if (transcurrido >= TIMEOUT_CONEXION_WIFI_MS) {
        break;
      }
      const unsigned long restante =
          TIMEOUT_CONEXION_WIFI_MS - transcurrido;
      delay(restante < 250 ? restante : 250);
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("Wi-Fi conectado correctamente.");
      Serial.print("Dirección IP del ESP32: ");
      Serial.println(WiFi.localIP());
      direccionIpMostrada = true;
      wifiEstabaConectado = true;
      configurarRutas();
    } else {
      Serial.print("Wi-Fi no conectado en 15 segundos. Estado: ");
      Serial.println(static_cast<int>(WiFi.status()));
      Serial.println("Se reintentará la conexión Wi-Fi desde loop().");
      ultimoIntentoWifi = millis();
    }
  } else {
    Serial.println(
        "Falta include/ecg_config.h: copie ecg_config.h.example y configure Wi-Fi y API.");
    ultimoMensaje =
        "Configuración incompleta: configure ecg_config.h y vuelva a cargar el firmware.";
  }

  Serial.println("Inicializando tarea de adquisición...");
  const BaseType_t tareaCreada = xTaskCreatePinnedToCore(
      tareaAdquisicion,
      "adquisicion_ecg",
      4096,
      nullptr,
      2,
      nullptr,
      1);
  if (tareaCreada != pdPASS) {
    Serial.println("Error: no se pudo iniciar la tarea de adquisición.");
    ultimoMensaje = "Error interno: no se pudo iniciar la tarea de adquisición.";
  }
  Serial.println("=== SETUP FINALIZADO ===");
}

void loop() {
  const bool wifiConectado = WiFi.status() == WL_CONNECTED;
  if (!wifiConectado) {
    direccionIpMostrada = false;

    if (reintentoWifiPendiente &&
        millis() - inicioReintentoWifi >= TIMEOUT_CONEXION_WIFI_MS) {
      Serial.print("Reintento Wi-Fi fallido. Estado: ");
      Serial.println(static_cast<int>(WiFi.status()));
      reintentoWifiPendiente = false;
      ultimoIntentoWifi = millis();
    }

    if (configuracionWifiValida &&
        !reintentoWifiPendiente &&
        millis() - ultimoIntentoWifi >= INTERVALO_REINTENTO_WIFI_MS) {
      ultimoIntentoWifi = millis();
      inicioReintentoWifi = ultimoIntentoWifi;
      reintentoWifiPendiente = true;
      Serial.println("Reintentando conexión Wi-Fi...");
      WiFi.begin(ECG_WIFI_SSID, ECG_WIFI_PASSWORD);
    }
  } else {
    reintentoWifiPendiente = false;
    if (!wifiEstabaConectado) {
      Serial.println("Wi-Fi conectado correctamente.");
    }
    wifiEstabaConectado = true;
    configurarRutas();
  }

  if (servidorHttpIniciado) {
    server.handleClient();
  }
  actualizarServiciosMdns();
  if (WiFi.status() == WL_CONNECTED && !direccionIpMostrada) {
    Serial.print("Direccion IP del ESP32: ");
    Serial.println(WiFi.localIP());
    direccionIpMostrada = true;
  }
  if (capturaLista &&
      (ultimoIntentoEnvio == 0 ||
       millis() - ultimoIntentoEnvio >= REINTENTO_ENVIO_MS)) {
    ultimoIntentoEnvio = millis();
    if (enviarCaptura()) {
      ultimoIntentoEnvio = 0;
    }
  }
  delay(1);
}
