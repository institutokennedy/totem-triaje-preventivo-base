#include <Arduino.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_system.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#if __has_include("ecg_config.h")
#include "ecg_config.h"
#else
#define ECG_WIFI_SSID ""
#define ECG_WIFI_PASSWORD ""
#define ECG_API_BASE_URL ""
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

WebServer server(80);
portMUX_TYPE capturaMux = portMUX_INITIALIZER_UNLOCKED;
uint16_t muestras[MUESTRAS_POR_CAPTURA] = {};
uint16_t muestrasCopia[MUESTRAS_POR_CAPTURA] = {};
volatile size_t cantidadMuestras = 0;
volatile bool adquisicionEnCurso = false;
volatile bool capturaLista = false;
volatile bool capturaAbortada = false;
volatile bool electrodosConectados = false;
volatile uint16_t ultimaMuestraADC = 0;
volatile int bpmEstimadoExperimental = 0;

int episodioId = 0;
int dispositivoId = 0;
bool configuracionWifiValida = false;
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

String origenApiConfigurado() {
  String base = ECG_API_BASE_URL;
  const int schemeEnd = base.indexOf("://");
  if (schemeEnd < 0) return "";
  const int pathStart = base.indexOf('/', schemeEnd + 3);
  if (pathStart >= 0) base.remove(pathStart);
  while (base.endsWith("/")) {
    base.remove(base.length() - 1);
  }
  return base;
}

void aplicarCabecerasCors() {
  const String origin = origenApiConfigurado();
  if (!origin.isEmpty()) {
    server.sendHeader("Access-Control-Allow-Origin", origin);
    server.sendHeader("Vary", "Origin");
  }
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
    responderError(503, "Configure Wi-Fi y la URL de la API en ecg_config.h.");
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
  capturaAbortada = false;
  capturaLista = false;
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
    actualizarEstimacionExperimental(muestra);
    portENTER_CRITICAL(&capturaMux);
    ultimaMuestraADC = muestra;
    if (adquisicionEnCurso && cantidadMuestras < MUESTRAS_POR_CAPTURA) {
      muestras[cantidadMuestras++] = muestra;
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

  size_t cantidad = 0;
  int episodio = 0;
  portENTER_CRITICAL(&capturaMux);
  cantidad = cantidadMuestras;
  if (cantidad == MUESTRAS_POR_CAPTURA && capturaLista) {
    memcpy(muestrasCopia, muestras, sizeof(muestrasCopia));
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
  payload.reserve(32000);
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
  payload += "],\"unidad\":\"ADC\",\"adquisicion_id\":\"";
  payload += id;
  payload += "\"}}";

  HTTPClient http;
  String apiBaseUrl = ECG_API_BASE_URL;
  while (apiBaseUrl.endsWith("/")) {
    apiBaseUrl.remove(apiBaseUrl.length() - 1);
  }
  const String url = apiBaseUrl + "/api/v1/ecg/resultados";
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
  uint16_t ultimaMuestra = 0;
  String id = adquisicionId;
  int bpm = 0;

  portENTER_CRITICAL(&capturaMux);
  cantidad = cantidadMuestras;
  enCurso = adquisicionEnCurso;
  pendiente = capturaLista;
  abortada = capturaAbortada;
  electrodos = electrodosConectados;
  ultimaMuestra = ultimaMuestraADC;
  bpm = bpmEstimadoExperimental;
  if (cantidad > 0) {
    memcpy(muestrasCopia, muestras, cantidad * sizeof(uint16_t));
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
  json.reserve(120 + cantidad * 6);
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
  json += "],\"codigo_http\":";
  json += String(ultimoCodigoHttp);
  json += ",\"mensaje\":\"";
  json += escaparJson(mensaje);
  json += "\"}";
  aplicarCabecerasCors();
  server.send(200, "application/json", json);
}

void configurarRutas() {
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
  server.begin();
}

}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(ECG_PIN, ADC_11db);

  configuracionWifiValida =
      strlen(ECG_WIFI_SSID) > 0 && strlen(ECG_WIFI_PASSWORD) > 0 &&
      strncmp(ECG_API_BASE_URL, "http://", 7) == 0;
  if (configuracionWifiValida) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(ECG_WIFI_SSID, ECG_WIFI_PASSWORD);
  } else {
    Serial.println(
        "Falta include/ecg_config.h: copie ecg_config.h.example y configure Wi-Fi y API.");
    ultimoMensaje =
        "Configuración incompleta: configure ecg_config.h y vuelva a cargar el firmware.";
  }

  configurarRutas();
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
  Serial.println("Monitor ECG disponible en la dirección IP del ESP32.");
}

void loop() {
  server.handleClient();
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
