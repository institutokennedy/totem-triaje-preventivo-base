import json
import math
import re
import shutil
import subprocess
from datetime import date
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, select

from app.common.models import (
    Dispositivo,
    EpisodioAtencion,
    Paciente,
    ResultadoModulo,
)
from app.core.database import get_session
from app.modules.ecg.router import router as ecg_router
from app.modules.ecg.schemas import (
    DatosECG,
    EntradaECG,
    EvaluacionPreventivaECG,
    MUESTRAS_CAPTURA_SENSOR,
    RespuestaConsulta,
)
from app.modules.ecg.preventive_assessment import (
    EvidenciaClinicaECG,
    _construir_evaluacion_preventiva,
    _evaluar_reglas,
    evaluar_captura_preventiva,
)
from app.modules.ecg.simulator import generar_datos_ecg


RUTA = "/api/v1/ecg/resultados"


@pytest.fixture()
def ecg_app(test_engine):
    SQLModel.metadata.create_all(test_engine)
    application = FastAPI()
    application.include_router(ecg_router)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session
    yield application
    application.dependency_overrides.clear()


@pytest.fixture()
def ecg_client(ecg_app):
    with TestClient(ecg_app) as test_client:
        yield test_client


@pytest.fixture()
def ecg_references(test_engine, ecg_app):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="12345678",
            nombre="Paciente",
            apellido="Ficticio",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        episodio = EpisodioAtencion(
            paciente_id=paciente.id,
            tipo_circuito="COMPLETO",
        )
        dispositivo = Dispositivo(
            codigo="ECG-001",
            nombre="Simulador ECG ficticio",
            tipo="ECG",
        )
        session.add(episodio)
        session.add(dispositivo)
        session.commit()
        session.refresh(episodio)
        session.refresh(dispositivo)

        return {
            "episodio_id": episodio.id,
            "dispositivo_id": dispositivo.id,
        }


def _entrada_valida(references):
    return {
        "episodio_id": references["episodio_id"],
        "dispositivo_id": references["dispositivo_id"],
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }


def _entrada_sensor_valida(references, adquisicion_id="00000000-0000-4000-8000-000000000099"):
    return {
        "episodio_id": references["episodio_id"],
        "dispositivo_id": references["dispositivo_id"],
        "origen": "SENSOR",
        "data": {
            "frecuencia_muestreo_hz": 250,
            "muestras": [2000 + (index % 100) for index in range(MUESTRAS_CAPTURA_SENSOR)],
            "unidad": "ADC",
            "adquisicion_id": adquisicion_id,
        },
    }


def _metadatos_calibracion_adc_sinteticos(estado="CALIBRADA"):
    return {
        "estado": estado,
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
        "error_codigo": None if estado == "CALIBRADA" else 259,
        "error": None if estado == "CALIBRADA" else "Fallo sintético de calibración",
    }


_FRONTEND_INTERACTION_HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const elements = new Map();
const tagPattern = /<([a-zA-Z][\w-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/g;
const repeatedCapture = {
  frecuencia_muestreo_hz: 250,
  muestras: [0.1, 0.3],
  unidad: "mV",
};
const previousAcquisitionId = "00000000-0000-4000-8000-000000000077";
const capturedSensorResult = {
  id: 88,
  data: {
    adquisicion_id: "00000000-0000-4000-8000-000000000088",
    frecuencia_muestreo_hz: 250,
    muestras: Array.from({ length: 2500 }, (_, index) => 1800 + (index % 200)),
    unidad: "ADC",
    muestras_mV_OUT: Array.from({ length: 2500 }, () => 1800),
    estado_mV_OUT: "NO_CONFIABLE",
    calibracion_adc: {
      estado: "NO_CONFIABLE",
      metodo: "ESP_IDF_LINE_FITTING",
      fuente: "EFUSE_VREF",
      vref_efuse_raw: 17,
      vref_efuse_mv: 1093,
      adc_unit: "ADC1",
      gpio: 34,
      canal: 6,
      resolucion_bits: 12,
      atenuacion: "ADC_11db/ADC_ATTEN_DB_12",
      chip_model: "ESP32-D0WD-V3",
      chip_revision: 301,
      esp_idf_version: "v5.5.5",
      error_codigo: null,
      error: "La API no puede verificar la procedencia.",
    },
  },
};

class Element {
  constructor(id, tag = "div", attributes = "") {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.attributes = {};
    this.listeners = {};
    this.dataset = {};
    this.hidden = /\shidden(?:\s|>)/.test(attributes);
    this.disabled = /\sdisabled(?:\s|>)/.test(attributes);
    this.checked = false;
    this.textContent = "";
    this.classList = { toggle() {} };
  }
  addEventListener(type, callback) {
    this.listeners[type] = callback;
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  setAttributeValue(name, value) {
    this.setAttribute(name, value);
  }
  replaceChildren(...children) { this.children = children; }
}

for (const match of input.html.matchAll(tagPattern)) {
  elements.set(match[3], new Element(match[3], match[1], match[2]));
}
const stepItems = Array.from({ length: 4 }, (_, index) => new Element(`step-${index}`, "li"));
const app = elements.get("ecg-app");
app.querySelector = (selector) => {
  if (selector.startsWith("#")) return elements.get(selector.slice(1));
  if (selector === "nav") return new Element("nav", "nav");
  if (selector === ".steps") return new Element("steps", "ol");
  throw new Error(`Selector no preparado en el test: ${selector}`);
};
app.querySelectorAll = (selector) => {
  if (selector === ".steps li") return stepItems;
  throw new Error(`Selector no preparado en el test: ${selector}`);
};

const calls = [];
const records = input.scenario === "repeat-no-save"
  ? [{ id: 77, data: { ...repeatedCapture, adquisicion_id: previousAcquisitionId } }]
  : [];
let simulatorRequests = 0;
let postRequests = 0;
let resultsRequests = 0;
let nextResultId = 100;
let nextIntervalId = 1;
let mockNow = Date.now();
const intervals = new Map();

function response(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

async function fetchMock(url, options = {}) {
  const method = options.method || "GET";
  const call = { url, method, body: options.body ? JSON.parse(options.body) : null };
  calls.push(call);

  if (url === "/api/v1/episodios/42") {
    return response(200, {
      id: 42, paciente_id: 8, tipo_circuito: "COMPLETO",
      estado: "INICIADO", iniciado_en: "2026-10-29T12:00:00Z",
    });
  }
  if (url === "/api/v1/dispositivos") {
    return response(200, [{
      id: 1, codigo: "ECG-001", tipo: "ECG", activo: true, estado: "DISPONIBLE",
    }]);
  }
  if (url === "/api/v1/ecg/simulador/captura") {
    simulatorRequests += 1;
    const data = input.scenario === "invalid-simulator"
      ? { frecuencia_muestreo_hz: 250, muestras: ["no-numérica"], unidad: "mV" }
      : { frecuencia_muestreo_hz: 250, muestras: [0.1, 0.3], unidad: "mV" };
    data.adquisicion_id = `00000000-0000-4000-8000-${String(simulatorRequests).padStart(12, "0")}`;
    return response(200, data);
  }
  if (url === "/api/v1/ecg/resultados/42") {
    resultsRequests += 1;
    if (input.scenario === "sensor-api-error" && resultsRequests === 1) {
      return response(503, { detail: "API temporalmente no disponible" });
    }
    if (input.scenario === "sensor-mode" && resultsRequests === 2) {
      return response(200, {
        episodio_id: 42, modulo: "ecg", resultados: [capturedSensorResult],
      });
    }
    if (input.scenario === "preflight-query-fails" && resultsRequests === 1) {
      return response(503, { detail: "Consulta no disponible" });
    }
    if (input.scenario === "uncertain-query-fails" && postRequests === 1 && resultsRequests === 2) {
      return response(503, { detail: "Consulta temporalmente no disponible" });
    }
    return response(200, { episodio_id: 42, modulo: "ecg", resultados: records });
  }
  if (url === "/api/v1/ecg/resultados" && method === "POST") {
    postRequests += 1;
    if (input.scenario === "post-422") {
      return response(422, { detail: [{ loc: ["body", "data"], msg: "muestras inválidas" }] });
    }
    const saved = { id: nextResultId++, data: call.body.data };
    records.push(saved);
    if (input.scenario === "uncertain-query-fails") {
      throw new Error("Conexión interrumpida después del guardado");
    }
    return response(201, { resultado_id: saved.id });
  }
  throw new Error(`Solicitud inesperada: ${method} ${url}`);
}

const context = {
  document: {
    getElementById: (id) => elements.get(id) || null,
    createElement: (tag) => new Element(`created-${nextIntervalId++}`, tag),
  },
  Error,
  Date: class extends Date {
    static now() { return mockNow; }
  },
  performance: { now: () => mockNow },
  Intl,
  URLSearchParams,
  window: {
    location: { search: "?episodio_id=42" },
    setTimeout: (callback) => queueMicrotask(callback),
    setInterval: (callback) => {
      const intervalId = nextIntervalId++;
      intervals.set(intervalId, callback);
      return intervalId;
    },
    clearInterval: (intervalId) => intervals.delete(intervalId),
    requestAnimationFrame: () => nextIntervalId++,
    cancelAnimationFrame: (frameId) => intervals.delete(frameId),
  },
  fetch: fetchMock,
};
vm.runInNewContext(input.javascript, context, { timeout: 5000 });

async function click(id) {
  const element = elements.get(id);
  if (!element || element.hidden || element.disabled || !element.listeners.click) return;
  await element.listeners.click({ target: element });
  await new Promise((resolve) => setImmediate(resolve));
}
async function waitForContext() {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await new Promise((resolve) => setImmediate(resolve));
    if (
      calls.some((call) => call.url === "/api/v1/dispositivos") &&
      !elements.get("iniciar-escucha").disabled
    ) return;
  }
  throw new Error("El contexto del episodio no terminó de cargar.");
}
async function prepareCapture() {
  await click("paso-siguiente");
  const checkbox = elements.get("aceptar-referencia-electrodos");
  checkbox.checked = true;
  await checkbox.listeners.change({ target: checkbox });
  await click("paso-siguiente");
  await click("iniciar-simulacion");
  await click("paso-siguiente");
}
async function run() {
  await waitForContext();
  if (
    input.scenario === "sensor-mode" ||
    input.scenario === "sensor-api-error" ||
    input.scenario === "sensor-disconnected"
  ) {
    const sensorMode = elements.get("modo-sensor");
    sensorMode.checked = true;
    await sensorMode.listeners.change({ target: sensorMode });
    await click("iniciar-escucha");
    const poll = intervals.values().next().value;
    if (input.scenario === "sensor-mode") {
      if (!poll) throw new Error("No se inició la consulta de capturas ESP32.");
      poll();
      await new Promise((resolve) => setImmediate(resolve));
      await new Promise((resolve) => setImmediate(resolve));
    } else if (input.scenario === "sensor-disconnected") {
      if (!poll) throw new Error("No se inició la consulta de capturas ESP32.");
      mockNow += 31000;
      poll();
      await new Promise((resolve) => setImmediate(resolve));
      await new Promise((resolve) => setImmediate(resolve));
    }
    return snapshot({});
  }

  await prepareCapture();

  if (input.scenario === "confirm-success") {
    await click("guardar-resultado");
  } else if (input.scenario === "repeat-no-save") {
    await click("repetir-simulacion");
    const postsAfterRepeat = postRequests;
    const recordsAfterRepeat = records.length;
    await click("paso-siguiente");
    await click("guardar-resultado");
    return snapshot({ postsAfterRepeat, recordsAfterRepeat });
  } else if (input.scenario === "post-422") {
    await click("guardar-resultado");
  } else if (input.scenario === "preflight-query-fails") {
    await click("guardar-resultado");
  } else if (input.scenario === "uncertain-query-fails") {
    await click("guardar-resultado");
    const simulatorCountWhileUncertain = simulatorRequests;
    const repeatDisabledWhileUncertain = elements.get("repetir-simulacion").disabled;
    const errorVisibleWhileUncertain = !elements.get("error").hidden;
    const errorWhileUncertain = elements.get("mensaje-error").textContent;
    await click("repetir-simulacion");
    const simulatorCountAfterBlockedRepeat = simulatorRequests;
    await click("verificar-resultado");
    return snapshot({
      simulatorCountWhileUncertain,
      repeatDisabledWhileUncertain,
      errorVisibleWhileUncertain,
      errorWhileUncertain,
      simulatorCountAfterBlockedRepeat,
    });
  } else if (input.scenario === "invalid-simulator") {
    await click("iniciar-simulacion");
  }

  return snapshot({});
}
function snapshot(extra) {
  return {
    ...extra,
    calls,
    records,
    simulatorRequests,
    postRequests,
    resultsRequests,
    error: elements.get("mensaje-error").textContent,
    errorVisible: !elements.get("error").hidden,
    status: elements.get("estado-guardado").textContent,
    confirmDisabled: elements.get("guardar-resultado").disabled,
    verificationDisabled: elements.get("verificar-resultado").disabled,
    graphLength: (elements.get("trazo-senal").attributes.d || "").length,
    deviceStatus: elements.get("estado-dispositivo").textContent,
    physicalStatus: elements.get("estado-fisico").textContent,
    timeAxis: elements.get("tiempo-total").textContent,
    source: elements.get("origen-resumen").textContent,
    unitLabel: elements.get("unidad-final").textContent,
    description: elements.get("descripcion-resumen").textContent,
    saveHidden: elements.get("guardar-resultado").hidden,
    sensorHistoryHidden: elements.get("capturas-historicas").hidden,
  };
}

run().then((result) => process.stdout.write(JSON.stringify(result))).catch((error) => {
  process.stderr.write(error.stack || String(error));
  process.exitCode = 1;
});
"""


def _run_frontend_interaction_test(ecg_client, scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Se necesita Node.js para ejecutar la prueba funcional del frontend ECG.")

    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text
    completed = subprocess.run(
        [node, "-e", _FRONTEND_INTERACTION_HARNESS],
        input=json.dumps(
            {"html": html, "javascript": javascript, "scenario": scenario}
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


_ASSESSMENT_RENDER_HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const elements = new Map();
class Element {
  constructor(id) {
    this.id = id;
    this.dataset = {};
    this.attributes = {};
    this.textContent = "";
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  replaceChildren(...children) { this.children = children; }
}
class NodeListMock {
  constructor(items) {
    this.items = items;
  }
  [Symbol.iterator]() { return this.items[Symbol.iterator](); }
  forEach(callback) { this.items.forEach(callback); }
}
const idPattern = /\bid="([^"]+)"/g;
for (const match of input.html.matchAll(idPattern)) {
  elements.set(match[1], new Element(match[1]));
}
const cards = [];
for (const match of input.html.matchAll(/<li\b([^>]*)>/g)) {
  const attributes = match[1];
  if (!/\bclass="[^"]*\bassessment-state\b[^"]*"/.test(attributes)) continue;
  const card = new Element(attributes.match(/\bid="([^"]+)"/)[1]);
  card.dataset.nivel = attributes.match(/\bdata-nivel="([^"]+)"/)[1];
  card.dataset.color = attributes.match(/\bdata-color="([^"]+)"/)[1];
  cards.push(card);
  elements.set(card.id, card);
}
const app = {
  querySelector(selector) { return elements.get(selector.slice(1)); },
  querySelectorAll(selector) {
    if (selector === ".assessment-state") return new NodeListMock(cards);
    throw new Error(`Selector no preparado: ${selector}`);
  },
};
const start = input.javascript.indexOf("  function renderAssessmentList(");
const end = input.javascript.indexOf("  function actualizarCapturaGuardada(", start);
if (start < 0 || end < 0) throw new Error("No se encontró el renderizador preventivo.");
const context = { app, document: { createElement: (tag) => new Element(tag) } };
vm.runInNewContext(input.javascript.slice(start, end), context, { timeout: 5000 });
context.renderPreventiveAssessment({ evaluacion_preventiva: input.assessment });
process.stdout.write(JSON.stringify({
  cards: cards.map((card) => ({
    nivel: card.dataset.nivel,
    color: card.dataset.color,
    selected: card.attributes["aria-current"] === "true",
  })),
  panelColor: elements.get("evaluacion-preventiva").dataset.color,
  nivel: elements.get("evaluacion-nivel").textContent,
  motivo: elements.get("evaluacion-motivo").textContent,
  datosTecnicos: elements.get("evaluacion-datos-tecnicos").textContent,
  reglas: (elements.get("evaluacion-reglas").children || [])
    .map((item) => item.textContent),
}));
"""


def _render_preventive_assessment(ecg_client, assessment):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Se necesita Node.js para probar el renderizado del semáforo ECG.")

    completed = subprocess.run(
        [node, "-e", _ASSESSMENT_RENDER_HARNESS],
        input=json.dumps(
            {
                "html": ecg_client.get("/api/v1/ecg/pantalla").text,
                "javascript": ecg_client.get("/api/v1/ecg/frontend.js").text,
                "assessment": assessment,
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


_SENSOR_PERSISTENCE_POLL_HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const values = new Map([
  ["estado-captura", { textContent: "" }],
  ["estado-guardado", { textContent: "" }],
  ["estado-dispositivo", { textContent: "" }],
  ["estado-fisico", { textContent: "" }],
  ["error", { hidden: true }],
  ["mensaje-error", { textContent: "" }],
]);
const app = { querySelector: (selector) => values.get(selector.slice(1)) };
let queryCount = 0;
const confirmed = [];
const context = {
  API: "/api/v1",
  MUESTRAS_CAPTURA: 2500,
  episodioActivo: { id: input.deviceState.episodio_id },
  app,
  requestJson: async () => {
    queryCount += 1;
    return input.httpResponse;
  },
  readDeviceState: async () => input.deviceState,
  setDeviceConnection: (status, detail) => {
    values.get("estado-dispositivo").textContent = `${status} ${detail}`;
  },
  updateLiveSignal: () => {},
  updateStartButton: () => {},
  setStatus: (message) => { values.get("estado-fisico").textContent = message; },
  reportError: (error) => {
    values.get("mensaje-error").textContent = error.message;
    values.get("error").hidden = false;
  },
  updateLiveSignalTrace: () => {},
  markLiveSignalDiscontinuity: () => {},
  liveSignalBuffer: {},
  esp32BaseUrl: "http://esp32.local",
  isCapturing: true,
  pollingGeneration: 1,
  pollingTimer: null,
  acquisitionId: null,
  sensorCapturesById: new Map(),
  actualizarListaCapturasFisicas: () => {},
  stopPolling: () => { context.isCapturing = false; },
  actualizarCapturaGuardada: (result) => {
    confirmed.push(result);
    values.get("estado-guardado").textContent =
      `Resultado guardado: la API confirmó la captura #${result.id}.`;
  },
  window: { setTimeout: () => 1 },
};
const helperStart = input.javascript.indexOf(
  "  async function obtenerResultadosPersistidos()"
);
const helperEnd = input.javascript.indexOf(
  "\n  function capturaSensorValida(", helperStart
);
const pollStart = input.javascript.indexOf("  async function pollAcquisition(");
const pollEnd = input.javascript.indexOf(
  "\n  async function esperarElectrodos(", pollStart
);
if (helperStart < 0 || helperEnd < 0 || pollStart < 0 || pollEnd < 0) {
  throw new Error("No se encontraron las funciones de consulta y polling.");
}
vm.runInNewContext(
  input.javascript.slice(helperStart, helperEnd) +
    input.javascript.slice(pollStart, pollEnd),
  context,
  { timeout: 5000 }
);
context.pollAcquisition("http://esp32.local", 1).then(() => {
  process.stdout.write(JSON.stringify({
    queryCount,
    confirmed: confirmed.length === 1,
    resultId: confirmed[0]?.id ?? null,
    guardStatus: values.get("estado-guardado").textContent,
    errorVisible: !values.get("error").hidden,
    error: values.get("mensaje-error").textContent,
    status: values.get("estado-fisico").textContent,
  }));
}).catch((error) => {
  process.stderr.write(error.stack || String(error));
  process.exitCode = 1;
});
"""


def _run_sensor_persistence_poll(ecg_client, http_response, acquisition_id):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Se necesita Node.js para probar el polling de persistencia ECG.")

    completed = subprocess.run(
        [node, "-e", _SENSOR_PERSISTENCE_POLL_HARNESS],
        input=json.dumps(
            {
                "javascript": ecg_client.get("/api/v1/ecg/frontend.js").text,
                "httpResponse": http_response,
                "deviceState": {
                    "episodio_id": http_response["episodio_id"],
                    "adquisicion_id": acquisition_id,
                    "backend_conectado": True,
                    "electrodos_conectados": True,
                    "adquisicion_en_curso": False,
                    "captura_pendiente": True,
                    "cantidad_muestras": MUESTRAS_CAPTURA_SENSOR,
                    "codigo_http": 201,
                    "mensaje": "Resultado guardado correctamente",
                },
            }
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


_LIVE_SIGNAL_BUFFER_HARNESS = r"""
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const context = {
  GRAFICA_X_INICIO: 72,
  GRAFICA_X_FIN: 620,
  GRAFICA_Y_INICIO: 20,
  GRAFICA_Y_FIN: 160,
  GRAFICA_PASO_X: 548 / 2500,
  app: {
    querySelector: (selector) => displayElements.get(selector),
  },
  isCapturing: true,
  liveSignalFrame: null,
  window: {
    requestAnimationFrame(callback) {
      animationFrames.push(callback);
      return animationFrames.length;
    },
    cancelAnimationFrame() {},
  },
};
const animationFrames = [];
const displayElements = new Map([
  "#amplitud-maxima", "#amplitud-centro-escala", "#amplitud-minima",
  "#unidad-eje", "#estado-escala-vertical", "#estado-integridad-senal",
].map((selector) => [selector, { textContent: "" }]));
displayElements.set("#trazo-grupo", {
  attributes: {},
  setAttribute(name, value) { this.attributes[name] = value; },
});
const start = input.javascript.indexOf("  function createLiveSignalBuffer(");
const end = input.javascript.indexOf("  function stopLiveSignalAnimation(", start);
if (start < 0 || end < 0) throw new Error("No se encontró el búfer circular ECG.");
vm.runInNewContext(input.javascript.slice(start, end), context, { timeout: 5000 });
const buffer = context.createLiveSignalBuffer(2500);
for (let count = 250; count <= 3000; count += 250) {
  context.appendLiveSignalState(buffer, {
    adquisicion_id: "captura-prueba",
    cantidad_muestras: count,
    muestras: Array.from({ length: count }, (_, index) => index % 4096),
    frecuencia_muestreo_hz: 250,
    unidad: "ADC",
  }, count * 4);
}
const path = context.liveSignalPath(buffer);
context.liveSignalBuffer = buffer;
context.animateLiveSignal();
animationFrames.shift()(12000);
const frameOffset = displayElements.get("#trazo-grupo").attributes.transform;
animationFrames.shift()(13000);
const nextFrameOffset = displayElements.get("#trazo-grupo").attributes.transform;
const gapBuffer = context.createLiveSignalBuffer(2500);
context.appendLiveSignalState(gapBuffer, {
  adquisicion_id: "captura-gap",
  cantidad_muestras: 2,
  muestras: [1000, 1001],
  frecuencia_muestreo_hz: 250,
  unidad: "ADC",
}, 0);
context.markLiveSignalDiscontinuity(gapBuffer);
context.appendLiveSignalState(gapBuffer, {
  adquisicion_id: "captura-gap",
  cantidad_muestras: 4,
  muestras: [1000, 1001, 1002, 1003],
  frecuencia_muestreo_hz: 250,
  unidad: "ADC",
}, 1000);
const completeBuffer = context.createLiveSignalBuffer(2500);
const completeSamples = Array.from({ length: 2500 }, (_, index) =>
  Math.round(index * 4095 / 2499)
);
context.appendLiveSignalState(completeBuffer, {
  adquisicion_id: "captura-completa",
  cantidad_muestras: 2500,
  muestras: completeSamples,
  frecuencia_muestreo_hz: 250,
  unidad: "ADC",
}, 10000);
const probeBuffer = context.createLiveSignalBuffer(3);
context.appendLiveSignalState(probeBuffer, {
  adquisicion_id: "captura-sonda",
  cantidad_muestras: 3,
  muestras: [0, 2048, 4095],
  frecuencia_muestreo_hz: 250,
  unidad: "ADC",
}, 0);
const centeredScale = context.visualAmplitudeScale([1800, 2048, 2300]);
context.updateSignalScaleStatus([0, 2048, 4095], 2047.5);
const adcSaturationStatus = displayElements.get("#estado-escala-vertical").textContent;
const adcAxisLabels = [
  displayElements.get("#amplitud-maxima").textContent,
  displayElements.get("#amplitud-centro-escala").textContent,
  displayElements.get("#amplitud-minima").textContent,
  displayElements.get("#unidad-eje").textContent,
];
context.updateSignalScaleStatus([1090, 1093, 1098], 1094, "mV_OUT");
process.stdout.write(JSON.stringify({
  size: buffer.size,
  capacity: buffer.capacity,
  firstSequence: buffer.sequences[buffer.head],
  lastSequence: buffer.lastSequence,
  retainedSequences: Array.from({ length: buffer.size }, (_, offset) =>
    buffer.sequences[(buffer.head + offset) % buffer.capacity]
  ),
  pathCommands: (path.match(/[ML]/g) || []).length,
  offsetAtSample: context.liveSignalOffset(buffer, 12000),
  offsetOneSecondLater: context.liveSignalOffset(buffer, 13000),
  frameOffset,
  nextFrameOffset,
  gapMoves: (context.liveSignalPath(gapBuffer).match(/M/g) || []).length,
  gapCount: gapBuffer.discontinuitiesCount,
  uniqueSequences: new Set(buffer.sequences.slice(0, buffer.size)).size,
  nominalWindowSeconds: completeBuffer.size / completeBuffer.frequency,
  completePath: context.liveSignalPath(completeBuffer),
  probePath: context.liveSignalPath(probeBuffer),
  centeredScale,
  saturationStatus: adcSaturationStatus,
  axisLabels: adcAxisLabels,
  calibratedStatus: displayElements.get("#estado-escala-vertical").textContent,
  calibratedAxis: displayElements.get("#unidad-eje").textContent,
}));
"""


def _simulate_live_signal_buffer(ecg_client):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Se necesita Node.js para probar el búfer visual ECG.")

    completed = subprocess.run(
        [node, "-e", _LIVE_SIGNAL_BUFFER_HARNESS],
        input=json.dumps(
            {"javascript": ecg_client.get("/api/v1/ecg/frontend.js").text}
        ),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_esquema_y_simulador_generan_datos_ecg_validos():
    datos = generar_datos_ecg()

    assert set(datos) == {
        "frecuencia_muestreo_hz",
        "muestras",
        "unidad",
    }
    assert DatosECG.model_validate(datos).model_dump(exclude_none=True) == datos
    assert generar_datos_ecg() == datos
    assert datos["frecuencia_muestreo_hz"] == 250
    assert len(datos["muestras"]) == 2500
    assert all(math.isfinite(muestra) for muestra in datos["muestras"])


def _evidencia_clinica_base(**cambios):
    evidencia = {
        "procedencia": "SINTETICA_PRUEBAS",
        "calidad_senal_valida": True,
        "colocacion_electrodos_correcta": True,
        "inversion_electrodos_detectada": False,
        "canales_ra_la_ll_disponibles": True,
        "impedancia_ra_ohm": 1000,
        "impedancia_la_ohm": 1000,
        "impedancia_ll_ohm": 1000,
        "excepciones_colocacion_evaluadas": True,
        "excepcion_colocacion_presente": False,
        "velocidad_papel_mm_s": 25,
        "ganancia_mm_por_mv": 10,
        "filtro_pasa_altos_hz": 0.05,
        "filtro_pasa_bajos_hz": 150,
        "filtros_configurados": True,
        "notch_50_hz_aplicado": True,
        "artefacto_excesivo": False,
        "snr_db": 20,
        "frecuencia_cardiaca_lpm": 75,
        "deteccion_picos_r_verificada": True,
        "algoritmo_picos_r": "PAN_TOMPKINS",
        "metodo_calculo_fc": "RR_REGULAR_300",
        "ritmo_regular_verificado": True,
        "rr_cuadros_grandes": 4,
        "rr_cuadros_pequenos": 20,
        "paciente_en_reposo": True,
        "atleta_alto_rendimiento": False,
        "paciente_pediatrico": False,
        "intervalos_rr_ms": [800, 800, 800],
        "qrs_ms": 80,
        "limites_qrs_verificados": True,
        "wolff_parkinson_white": False,
        "ritmo_marcapasos": False,
        "pr_ms": 160,
        "onda_p_clara": True,
        "ritmo_sinusal": True,
        "qt_ms": 400,
        "rr_previo_ms": 800,
        "qtc_ms": 440,
        "qtc_verificado": True,
        "qtc_coherente_con_qt_rr_y_metodo": True,
        "sexo_regla_qtc": "H",
        "metodo_qtc": "BAZETT",
        "st_desviacion_mv": 0,
        "adulto": True,
        "linea_isoestable": True,
        "punto_j_medido": True,
        "amplitud_calibrada_mv": True,
        "excepcion_st_t_presente": False,
    }
    evidencia.update(cambios)
    return EvidenciaClinicaECG.model_validate(evidencia)


def _evaluar_regla(
    identificador,
    evidencia=None,
    frecuencia=500,
    unidad="mV",
    cantidad_muestras=MUESTRAS_CAPTURA_SENSOR,
):
    valores_muestra = {
        "frecuencia_muestreo_hz": frecuencia,
        "muestras": [0.1] * cantidad_muestras,
        "unidad": unidad,
    }
    if cantidad_muestras > MUESTRAS_CAPTURA_SENSOR:
        datos = DatosECG.model_construct(**valores_muestra)
    else:
        datos = DatosECG(**valores_muestra)
    reglas = _evaluar_reglas(datos, evidencia)
    evaluacion = _construir_evaluacion_preventiva(datos, reglas)
    return evaluacion, next(
        regla for regla in evaluacion.reglas
        if regla.identificador == identificador
    )


def test_evaluacion_preventiva_no_clasifica_como_normal_senal_adc_actual():
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[2048] * MUESTRAS_CAPTURA_SENSOR,
        unidad="ADC",
    )

    evaluacion = evaluar_captura_preventiva(datos)

    assert evaluacion.nivel == "NO_EVALUABLE"
    assert evaluacion.color == "GRIS"
    assert evaluacion.parametros_evaluados == ["RC-ECG-002"]
    assert evaluacion.valores_medidos == {
        "RC-ECG-002.frecuencia_muestreo_hz": 250.0,
    }
    assert evaluacion.criterios_activados == ["RC-ECG-002"]
    assert evaluacion.calidad_senal == "NO EVALUADA O INSUFICIENTE"
    assert evaluacion.datos_tecnicos.cantidad_muestras == MUESTRAS_CAPTURA_SENSOR
    assert evaluacion.datos_tecnicos.frecuencia_muestreo_hz == 250
    assert any("al menos 500 Hz" in item for item in evaluacion.advertencias_tecnicas)
    assert any("no se convierten a mV" in item for item in evaluacion.advertencias_tecnicas)
    assert "normalidad" in evaluacion.motivo
    assert len(evaluacion.reglas) == 9
    assert [rule.estado for rule in evaluacion.reglas] == [
        "NO_EVALUABLE",
        "NO_CUMPLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
        "NO_EVALUABLE",
    ]
    assert len(evaluacion.parametros_no_evaluables) == 8
    assert "LO+/LO−" in evaluacion.parametros_no_evaluables[0]
    assert "250 Hz" in evaluacion.reglas[1].motivo
    assert evaluacion.metricas_tecnicas.duracion_entre_muestras_segundos == pytest.approx(
        (MUESTRAS_CAPTURA_SENSOR - 1) / 250
    )
    assert evaluacion.metricas_tecnicas.amplitud_minima == 2048
    assert evaluacion.metricas_tecnicas.amplitud_maxima == 2048
    assert evaluacion.metricas_tecnicas.amplitud_rango == 0
    assert evaluacion.metricas_tecnicas.muestras_distintas == 1
    assert evaluacion.metricas_tecnicas.muestras_adc_en_riel_inferior == 0
    assert evaluacion.metricas_tecnicas.muestras_adc_en_riel_superior == 0


@pytest.mark.parametrize(
    ("evidence_changes", "expected"),
    [
        ({}, "CUMPLE"),
        ({"colocacion_electrodos_correcta": False}, "NO_CUMPLE"),
        ({"inversion_electrodos_detectada": True}, "NO_CUMPLE"),
        ({"canales_ra_la_ll_disponibles": False}, "NO_EVALUABLE"),
        ({"impedancia_ra_ohm": None}, "NO_EVALUABLE"),
        ({"excepciones_colocacion_evaluadas": None}, "NO_EVALUABLE"),
        ({"excepcion_colocacion_presente": True}, "NO_EVALUABLE"),
        ({"colocacion_electrodos_correcta": None}, "NO_EVALUABLE"),
    ],
)
def test_rc_ecg_001_evalua_colocacion_solo_con_verificacion_y_impedancias(
    evidence_changes, expected
):
    _, rule = _evaluar_regla(
        "RC-ECG-001", _evidencia_clinica_base(**evidence_changes)
    )

    assert rule.estado == expected


@pytest.mark.parametrize(
    ("frequency", "evidence_changes", "expected"),
    [
        (499, {}, "NO_CUMPLE"),
        (500, {}, "CUMPLE"),
        (500, {"snr_db": 14.99}, "NO_CUMPLE"),
        (500, {"velocidad_papel_mm_s": 24.9}, "NO_CUMPLE"),
        (500, {"filtro_pasa_altos_hz": None}, "NO_EVALUABLE"),
        (500, {"ritmo_marcapasos": None}, "NO_EVALUABLE"),
        (500, {"ritmo_marcapasos": True, "filtro_pasa_bajos_hz": 250}, "CUMPLE"),
        (500, {"ritmo_marcapasos": True, "filtro_pasa_bajos_hz": 150}, "NO_CUMPLE"),
    ],
)
def test_rc_ecg_002_evalua_requisitos_tecnicos_y_snr(
    frequency, evidence_changes, expected
):
    _, rule = _evaluar_regla(
        "RC-ECG-002",
        _evidencia_clinica_base(**evidence_changes),
        frecuencia=frequency,
    )

    assert rule.estado == expected


@pytest.mark.parametrize(
    ("heart_rate", "expected"),
    [(49, "NO_CUMPLE"), (50, "NO_EVALUABLE"), (120, "NO_EVALUABLE"), (125, "NO_CUMPLE")],
)
def test_rc_ecg_003_aplica_solo_los_cortes_de_alerta_explicitos(
    heart_rate, expected
):
    _, rule = _evaluar_regla(
        "RC-ECG-003",
        _evidencia_clinica_base(
            frecuencia_cardiaca_lpm=heart_rate,
            rr_cuadros_grandes=300 / heart_rate,
        ),
    )

    assert rule.estado == expected


@pytest.mark.parametrize(
    "evidence_changes",
    [
        {"deteccion_picos_r_verificada": None},
        {"deteccion_picos_r_verificada": False},
        {"algoritmo_picos_r": None},
        {"metodo_calculo_fc": None},
        {"ritmo_regular_verificado": None},
        {"rr_cuadros_grandes": None},
        {"frecuencia_cardiaca_lpm": 74},
    ],
)
def test_rc_ecg_003_no_evalua_frecuencia_sin_deteccion_y_metodo_requeridos(
    evidence_changes,
):
    _, rule = _evaluar_regla(
        "RC-ECG-003",
        _evidencia_clinica_base(**evidence_changes),
    )

    assert rule.estado == "NO_EVALUABLE"


def test_rc_ecg_003_exige_metodo_coherente_con_regularidad_verificada():
    _, rule = _evaluar_regla(
        "RC-ECG-003",
        _evidencia_clinica_base(ritmo_regular_verificado=False),
    )

    assert rule.estado == "NO_EVALUABLE"
    assert "no corresponde" in rule.motivo


@pytest.mark.parametrize(
    ("method", "regular", "qrs_count", "count", "expected"),
    [
        ("QRS_6S_X10", False, 4, 3001, "NO_CUMPLE"),
        ("QRS_6S_X10", False, 4, 2500, "NO_EVALUABLE"),
        ("QRS_10S_X6", False, 4, 5001, "NO_CUMPLE"),
        ("RR_REGULAR_1500", True, None, 2500, "NO_EVALUABLE"),
    ],
)
def test_rc_ecg_003_aplica_formula_y_ventana_documentadas(
    method, regular, qrs_count, count, expected
):
    changes = {
        "ritmo_regular_verificado": regular,
        "metodo_calculo_fc": method,
        "qrs_contados": qrs_count,
    }
    if method == "QRS_6S_X10":
        changes["frecuencia_cardiaca_lpm"] = qrs_count * 10
    elif method == "QRS_10S_X6":
        changes["frecuencia_cardiaca_lpm"] = qrs_count * 6
    else:
        changes["frecuencia_cardiaca_lpm"] = 75
    _, rule = _evaluar_regla(
        "RC-ECG-003",
        _evidencia_clinica_base(**changes),
        cantidad_muestras=count,
    )

    assert rule.estado == expected


def test_rc_ecg_003_no_acepta_fc_inconsistente_con_formula_de_rr():
    _, rule = _evaluar_regla(
        "RC-ECG-003",
        _evidencia_clinica_base(
            frecuencia_cardiaca_lpm=74,
            rr_cuadros_grandes=4,
        ),
    )

    assert rule.estado == "NO_EVALUABLE"
    assert "no coincide" in rule.motivo


def test_rc_ecg_003_rechaza_algoritmo_de_picos_r_no_documentado():
    with pytest.raises(ValidationError):
        _evidencia_clinica_base(algoritmo_picos_r="NO_VALIDADO")


@pytest.mark.parametrize(
    "evidence_changes",
    [
        {"intervalos_rr_ms": [800, 800, 800]},
        {"intervalos_rr_ms": [800, 900, 1100]},
        {"intervalos_rr_ms": None},
    ],
)
def test_rc_ecg_004_no_inventa_cortes_de_regularidad(evidence_changes):
    _, rule = _evaluar_regla(
        "RC-ECG-004", _evidencia_clinica_base(**evidence_changes)
    )

    assert rule.estado == "NO_EVALUABLE"
    assert "al menos 10 segundos" in rule.motivo


def test_rc_ecg_005_no_evalua_fa_sin_derivacion_deteccion_y_severidad_resuelta():
    _, rule = _evaluar_regla(
        "RC-ECG-005", _evidencia_clinica_base()
    )

    assert rule.estado == "NO_EVALUABLE"
    assert "DII/V1" in rule.motivo
    assert "amarillo-roja" in rule.motivo


@pytest.mark.parametrize(
    ("qrs_ms", "expected"),
    [
        (99.9, "CUMPLE"),
        (100, "NO_CUMPLE"),
        (119, "NO_CUMPLE"),
        (119.5, "NO_EVALUABLE"),
        (120, "NO_CUMPLE"),
        (130, "NO_CUMPLE"),
    ],
)
def test_rc_ecg_006_clasifica_solo_los_rangos_qrs_especificados(qrs_ms, expected):
    _, rule = _evaluar_regla(
        "RC-ECG-006", _evidencia_clinica_base(qrs_ms=qrs_ms)
    )

    assert rule.estado == expected


@pytest.mark.parametrize(
    ("pr_ms", "expected"),
    [
        (119.9, "NO_CUMPLE"),
        (120, "CUMPLE"),
        (200, "CUMPLE"),
        (200.1, "NO_CUMPLE"),
    ],
)
def test_rc_ecg_007_clasifica_pr_y_los_limites_inclusivos(pr_ms, expected):
    _, rule = _evaluar_regla(
        "RC-ECG-007", _evidencia_clinica_base(pr_ms=pr_ms)
    )

    assert rule.estado == expected


def test_rc_ecg_007_no_evalua_ritmo_no_sinusal():
    _, rule = _evaluar_regla(
        "RC-ECG-007", _evidencia_clinica_base(ritmo_sinusal=False)
    )

    assert rule.estado == "NO_EVALUABLE"


@pytest.mark.parametrize(
    ("qtc_ms", "sexo", "expected"),
    [
        (450, "H", "CUMPLE"),
        (460, "M", "CUMPLE"),
        (451, "H", "NO_EVALUABLE"),
        (470, "M", "NO_EVALUABLE"),
        (500, "H", "NO_EVALUABLE"),
        (500.01, "H", "NO_CUMPLE"),
    ],
)
def test_rc_ecg_008_usa_limites_claros_y_deja_tramo_ambiguo_no_evaluable(
    qtc_ms, sexo, expected
):
    _, rule = _evaluar_regla(
        "RC-ECG-008",
        _evidencia_clinica_base(qtc_ms=qtc_ms, sexo_regla_qtc=sexo),
    )

    assert rule.estado == expected


def test_rc_ecg_008_no_calcula_con_formula_ambigua_o_metodo_inconsistente():
    _, unverified = _evaluar_regla(
        "RC-ECG-008", _evidencia_clinica_base(qtc_verificado=False)
    )
    _, incoherent = _evaluar_regla(
        "RC-ECG-008",
        _evidencia_clinica_base(qtc_coherente_con_qt_rr_y_metodo=False),
    )
    _, coherence_missing = _evaluar_regla(
        "RC-ECG-008",
        _evidencia_clinica_base(qtc_coherente_con_qt_rr_y_metodo=None),
    )
    _, wrong_method = _evaluar_regla(
        "RC-ECG-008",
        _evidencia_clinica_base(metodo_qtc="FRIDERICIA"),
    )

    assert unverified.estado == "NO_EVALUABLE"
    assert "fórmula ambigua" in unverified.motivo
    assert incoherent.estado == "NO_EVALUABLE"
    assert coherence_missing.estado == "NO_EVALUABLE"
    assert wrong_method.estado == "NO_EVALUABLE"


@pytest.mark.parametrize(
    ("st_mv", "expected"),
    [(0.1, "NO_CUMPLE"), (-0.1, "NO_CUMPLE"), (0.099, "NO_EVALUABLE")],
)
def test_rc_ecg_009_aplica_corte_st_solo_con_calibracion_y_punto_j(
    st_mv, expected
):
    _, rule = _evaluar_regla(
        "RC-ECG-009",
        _evidencia_clinica_base(st_desviacion_mv=st_mv),
    )

    assert rule.estado == expected


@pytest.mark.parametrize(
    "evidence_changes",
    [
        {"amplitud_calibrada_mv": False},
        {"punto_j_medido": False},
        {"linea_isoestable": False},
        {"excepcion_st_t_presente": True},
    ],
)
def test_rc_ecg_009_no_evalua_sin_calibracion_referencia_o_con_excepcion(
    evidence_changes,
):
    _, rule = _evaluar_regla(
        "RC-ECG-009",
        _evidencia_clinica_base(**evidence_changes),
    )

    assert rule.estado == "NO_EVALUABLE"


def test_evaluador_rechaza_evidencia_no_finita():
    with pytest.raises(ValidationError):
        _evidencia_clinica_base(snr_db=float("nan"))


def test_evaluador_publico_rechaza_fixtures_sinteticos_como_evidencia_clinica():
    datos = DatosECG(
        frecuencia_muestreo_hz=500,
        muestras=[0.1] * MUESTRAS_CAPTURA_SENSOR,
        unidad="mV",
    )

    with pytest.raises(ValueError, match="fixtures sintéticos"):
        evaluar_captura_preventiva(datos, _evidencia_clinica_base())


@pytest.mark.parametrize(
    ("evidence", "expected_level", "expected_color"),
    [
        (None, "NO_EVALUABLE", "GRIS"),
        (_evidencia_clinica_base(qrs_ms=130), "AMARILLO", "AMARILLO"),
        (_evidencia_clinica_base(qtc_ms=501), "ROJO", "ROJO"),
    ],
)
def test_semaforo_backend_prioriza_rojo_y_no_marca_normal_con_reglas_incompletas(
    evidence, expected_level, expected_color
):
    evaluation, _ = _evaluar_regla("RC-ECG-006", evidence)

    assert evaluation.nivel == expected_level
    assert evaluation.color == expected_color
    assert next(
        rule for rule in evaluation.reglas
        if rule.identificador == "RC-ECG-004"
    ).estado == "NO_EVALUABLE"
    assert next(
        rule for rule in evaluation.reglas
        if rule.identificador == "RC-ECG-005"
    ).estado == "NO_EVALUABLE"


def test_evaluacion_preventiva_muestras_incompletas_sigue_no_evaluable():
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[0.1],
        unidad="mV",
    )

    evaluacion = evaluar_captura_preventiva(datos)

    assert evaluacion.nivel == "NO_EVALUABLE"
    assert evaluacion.color == "GRIS"
    assert evaluacion.datos_tecnicos.cantidad_muestras == 1
    assert evaluacion.parametros_evaluados == ["RC-ECG-002"]
    assert evaluacion.calidad_senal == "NO EVALUADA O INSUFICIENTE"


def test_evaluacion_preventiva_no_pasa_a_verde_solo_por_superar_frecuencia():
    datos = DatosECG(
        frecuencia_muestreo_hz=500,
        muestras=[0.0] * 2500,
        unidad="mV",
    )

    evaluacion = evaluar_captura_preventiva(datos)

    assert evaluacion.nivel == "NO_EVALUABLE"
    assert evaluacion.color == "GRIS"
    assert evaluacion.parametros_evaluados == []
    assert evaluacion.valores_medidos == {}
    assert all(
        f"RC-ECG-{rule_id:03d}" in evaluacion.parametros_no_evaluables[rule_id - 1]
        for rule_id in range(1, 10)
    )
    assert "menor que 500 Hz" not in evaluacion.parametros_no_evaluables[1]


@pytest.mark.parametrize(
    ("frequency", "expects_below_minimum"),
    [(499, True), (500, False), (501, False)],
)
def test_frecuencia_minima_documentada_no_habilita_clasificacion_clinica(
    frequency, expects_below_minimum
):
    datos = DatosECG(
        frecuencia_muestreo_hz=frequency,
        muestras=[0.0] * frequency,
        unidad="mV",
    )

    evaluation = evaluar_captura_preventiva(datos)
    quality_requirement = next(
        rule for rule in evaluation.reglas
        if rule.identificador == "RC-ECG-002"
    ).motivo

    assert evaluation.nivel == "NO_EVALUABLE"
    assert evaluation.color == "GRIS"
    assert ("al menos 500 Hz" in quality_requirement) is expects_below_minimum


@pytest.mark.parametrize(
    ("samples", "low_rail_count", "high_rail_count"),
    [
        ([0, 1, 2048, 4094, 4095], 1, 1),
        ([1, 2048, 4094], 0, 0),
        ([0, 0, 4095, 4095], 2, 2),
    ],
)
def test_metricas_tecnicas_cuentan_saturacion_adc_en_extremos(
    samples, low_rail_count, high_rail_count
):
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=samples,
        unidad="ADC",
    )

    metrics = evaluar_captura_preventiva(datos).metricas_tecnicas

    assert metrics.amplitud_minima == min(samples)
    assert metrics.amplitud_maxima == max(samples)
    assert metrics.amplitud_rango == max(samples) - min(samples)
    assert metrics.muestras_distintas == len(set(samples))
    assert metrics.muestras_adc_en_riel_inferior == low_rail_count
    assert metrics.muestras_adc_en_riel_superior == high_rail_count


def test_metricas_tecnicas_no_inventan_rieles_para_muestras_mv():
    datos = DatosECG(
        frecuencia_muestreo_hz=500,
        muestras=[-0.1, 0.0, 0.2],
        unidad="mV",
    )

    evaluation = evaluar_captura_preventiva(datos)
    metrics = evaluation.metricas_tecnicas

    assert metrics.muestras_adc_en_riel_inferior is None
    assert metrics.muestras_adc_en_riel_superior is None
    assert metrics.duracion_entre_muestras_segundos == pytest.approx(2 / 500)
    assert evaluation.nivel == "NO_EVALUABLE"
    assert evaluation.color == "GRIS"


def test_frontend_presenta_metricas_tecnicas_devueltas_por_backend(ecg_client):
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[0, 100, 4095],
        unidad="ADC",
    )
    assessment = evaluar_captura_preventiva(datos)

    rendered = _render_preventive_assessment(
        ecg_client, assessment.model_dump(mode="json")
    )

    assert "3 muestras · 250 Hz · ADC" in rendered["datosTecnicos"]
    assert "intervalo entre muestras: 0.008 s" in rendered["datosTecnicos"]
    assert "rango: 0–4095 (4095)" in rendered["datosTecnicos"]
    assert "muestras ADC en 0/4095: 1/1" in rendered["datosTecnicos"]


def _reglas_sinteticas_cumplen():
    return [
        {
            "identificador": f"RC-ECG-{rule_id:03d}",
            "estado": "CUMPLE",
            "motivo": "Fixture sintético para validar solo la estructura del esquema.",
            "valores_medidos": {"medicion_sintetica": float(rule_id)},
        }
        for rule_id in range(1, 10)
    ]


@pytest.mark.parametrize(
    ("nivel", "color"),
    [
        ("VERDE", "VERDE"),
        ("AMARILLO", "AMARILLO"),
        ("ROJO", "ROJO"),
        ("NO_EVALUABLE", "GRIS"),
    ],
)
def test_esquema_evaluacion_admite_los_cuatro_estados(nivel, color):
    synthetic_green_fixture = nivel == "VERDE"
    evaluacion = EvaluacionPreventivaECG(
        nivel=nivel,
        color=color,
        motivo="Justificación del estado recibido.",
        parametros_evaluados=(
            [f"RC-ECG-{rule_id:03d}" for rule_id in range(1, 10)]
            if synthetic_green_fixture
            else []
        ),
        valores_medidos=(
            {
                f"RC-ECG-{rule_id:03d}.medicion_sintetica": float(rule_id)
                for rule_id in range(1, 10)
            }
            if synthetic_green_fixture
            else {}
        ),
        criterios_activados=[],
        parametros_no_evaluables=[],
        calidad_senal=(
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA"
            if synthetic_green_fixture
            else "NO EVALUADA"
        ),
        datos_tecnicos={
            "frecuencia_muestreo_hz": 500 if synthetic_green_fixture else 250,
            "cantidad_muestras": 5001 if synthetic_green_fixture else MUESTRAS_CAPTURA_SENSOR,
            "unidad": "mV" if synthetic_green_fixture else "ADC",
        },
        advertencias_tecnicas=[],
        reglas=_reglas_sinteticas_cumplen() if synthetic_green_fixture else [],
    )

    assert evaluacion.nivel == nivel
    assert evaluacion.color == color


@pytest.mark.parametrize(
    ("rules", "quality", "non_evaluable", "frequency", "count", "unit"),
    [
        (
            _reglas_sinteticas_cumplen()[:-1],
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            500,
            5001,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen()[:4]
            + [{
                **_reglas_sinteticas_cumplen()[4],
                "estado": "NO_EVALUABLE",
            }]
            + _reglas_sinteticas_cumplen()[5:],
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            500,
            5001,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen(),
            "NO EVALUADA",
            [],
            500,
            5001,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen(),
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            ["RC-ECG-004: falta evidencia"],
            500,
            5001,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen(),
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            250,
            MUESTRAS_CAPTURA_SENSOR,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen(),
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            500,
            MUESTRAS_CAPTURA_SENSOR,
            "mV",
        ),
        (
            _reglas_sinteticas_cumplen(),
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            500,
            5001,
            "ADC",
        ),
        (
            _reglas_sinteticas_cumplen()[:1]
            + [{
                **_reglas_sinteticas_cumplen()[1],
                "valores_medidos": {},
            }]
            + _reglas_sinteticas_cumplen()[2:],
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
            [],
            500,
            5001,
            "mV",
        ),
    ],
)
def test_esquema_rechaza_verde_incompleto_o_sin_calidad_apta(
    rules, quality, non_evaluable, frequency, count, unit
):
    with pytest.raises(ValidationError):
        EvaluacionPreventivaECG(
            nivel="VERDE",
            color="VERDE",
            motivo="Fixture sintético; no es una evaluación clínica.",
            parametros_evaluados=[f"RC-ECG-{rule_id:03d}" for rule_id in range(1, 10)],
            valores_medidos={
                f"RC-ECG-{rule_id:03d}.medicion_sintetica": float(rule_id)
                for rule_id in range(1, 10)
            },
            criterios_activados=[],
            parametros_no_evaluables=non_evaluable,
            calidad_senal=quality,
            datos_tecnicos={
                "frecuencia_muestreo_hz": frequency,
                "cantidad_muestras": count,
                "unidad": unit,
            },
            advertencias_tecnicas=[],
            reglas=rules,
        )


@pytest.mark.parametrize(
    ("nivel", "color", "parametros_evaluados", "valores_medidos"),
    [
        ("VERDE", "GRIS", ["PR"], {"PR_ms": 160}),
        ("VERDE", "VERDE", [], {}),
    ],
)
def test_esquema_rechaza_estado_inconsistente_o_verde_sin_mediciones(
    nivel, color, parametros_evaluados, valores_medidos
):
    with pytest.raises(ValidationError):
        EvaluacionPreventivaECG(
            nivel=nivel,
            color=color,
            motivo="Justificación del estado recibido.",
            parametros_evaluados=parametros_evaluados,
            valores_medidos=valores_medidos,
            criterios_activados=[],
            parametros_no_evaluables=[],
            calidad_senal="NO EVALUADA",
            datos_tecnicos={
                "frecuencia_muestreo_hz": 250,
                "cantidad_muestras": MUESTRAS_CAPTURA_SENSOR,
                "unidad": "ADC",
            },
            advertencias_tecnicas=[],
        )


@pytest.mark.parametrize(
    ("nivel", "color"),
    [
        ("VERDE", "VERDE"),
        ("AMARILLO", "AMARILLO"),
        ("ROJO", "ROJO"),
        ("NO_EVALUABLE", "GRIS"),
    ],
)
def test_frontend_destaca_estado_y_motivo_recibidos_del_backend(
    ecg_client, nivel, color
):
    synthetic_green_fixture = nivel == "VERDE"
    assessment = EvaluacionPreventivaECG(
        nivel=nivel,
        color=color,
        motivo=f"Motivo recibido para {nivel}.",
        parametros_evaluados=(
            [f"RC-ECG-{rule_id:03d}" for rule_id in range(1, 10)]
            if synthetic_green_fixture
            else []
        ),
        valores_medidos=(
            {
                f"RC-ECG-{rule_id:03d}.medicion_sintetica": float(rule_id)
                for rule_id in range(1, 10)
            }
            if synthetic_green_fixture
            else {}
        ),
        criterios_activados=[],
        parametros_no_evaluables=[],
        calidad_senal=(
            "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA"
            if synthetic_green_fixture
            else "NO EVALUADA"
        ),
        datos_tecnicos={
            "frecuencia_muestreo_hz": 500 if synthetic_green_fixture else 250,
            "cantidad_muestras": 5001 if synthetic_green_fixture else MUESTRAS_CAPTURA_SENSOR,
            "unidad": "mV" if synthetic_green_fixture else "ADC",
        },
        advertencias_tecnicas=[],
        reglas=_reglas_sinteticas_cumplen() if synthetic_green_fixture else [],
    )

    rendered = _render_preventive_assessment(
        ecg_client, assessment.model_dump(mode="json")
    )

    assert sum(card["selected"] for card in rendered["cards"]) == 1
    selected = next(card for card in rendered["cards"] if card["selected"])
    assert (selected["nivel"], selected["color"]) == (nivel, color)
    assert rendered["nivel"].startswith(nivel)
    assert rendered["nivel"].endswith(color)
    assert rendered["motivo"] == f"Motivo recibido para {nivel}."
    assert rendered["panelColor"] == color.lower()


def test_frontend_captura_actual_se_muestra_gris(ecg_client):
    data = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[2048] * MUESTRAS_CAPTURA_SENSOR,
        unidad="ADC",
    )
    assessment = evaluar_captura_preventiva(data)

    rendered = _render_preventive_assessment(
        ecg_client, assessment.model_dump(mode="json")
    )

    selected = [card for card in rendered["cards"] if card["selected"]]
    assert [(card["nivel"], card["color"]) for card in selected] == [
        ("NO_EVALUABLE", "GRIS")
    ]
    assert rendered["nivel"].startswith("NO_EVALUABLE")
    assert rendered["nivel"].endswith("GRIS")
    assert rendered["motivo"] == assessment.motivo


def test_frontend_muestra_resultados_individuales_devuelto_por_backend(ecg_client):
    evidence = _evidencia_clinica_base(
        frecuencia_cardiaca_lpm=48,
        rr_cuadros_grandes=6.25,
    )
    assessment, _ = _evaluar_regla("RC-ECG-003", evidence)

    rendered = _render_preventive_assessment(
        ecg_client, assessment.model_dump(mode="json")
    )

    assert rendered["nivel"] == "AMARILLO · AMARILLO"
    assert len(rendered["reglas"]) == 9
    assert any(
        item.startswith("RC-ECG-003 · NO_CUMPLE:")
        for item in rendered["reglas"]
    )
    assert any(
        item.startswith("RC-ECG-004 · NO_EVALUABLE:")
        for item in rendered["reglas"]
    )


def test_frontend_datos_incompletos_no_se_muestran_verdes(ecg_client):
    rendered = _render_preventive_assessment(
        ecg_client,
        {"nivel": "VERDE", "color": "VERDE", "motivo": "Sin alertas."},
    )

    selected = [card for card in rendered["cards"] if card["selected"]]
    assert [(card["nivel"], card["color"]) for card in selected] == [
        ("NO_EVALUABLE", "GRIS")
    ]
    assert rendered["nivel"].startswith("NO EVALUABLE")
    assert rendered["nivel"].endswith("GRIS")
    assert "no se puede inferir normalidad" in rendered["motivo"]


@pytest.mark.parametrize(
    "invalid_condition",
    [
        "rule_non_evaluable",
        "missing_rule",
        "low_frequency",
        "short_capture",
        "adc_units",
        "quality_not_apt",
        "pending_rule",
    ],
)
def test_frontend_rechaza_verde_si_reglas_o_calidad_no_son_validas(
    ecg_client, invalid_condition
):
    assessment = {
        "nivel": "VERDE",
        "color": "VERDE",
        "motivo": "Fixture sintético; no es una evaluación clínica.",
        "parametros_evaluados": [
            f"RC-ECG-{rule_id:03d}" for rule_id in range(1, 10)
        ],
        "valores_medidos": {"fixture_sintetico": 1.0},
        "criterios_activados": [],
        "parametros_no_evaluables": [],
        "calidad_senal": "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA",
        "datos_tecnicos": {
            "frecuencia_muestreo_hz": 500,
            "cantidad_muestras": 5001,
            "unidad": "mV",
        },
        "advertencias_tecnicas": [],
        "reglas": _reglas_sinteticas_cumplen(),
    }
    if invalid_condition == "rule_non_evaluable":
        assessment["reglas"][3]["estado"] = "NO_EVALUABLE"
    elif invalid_condition == "missing_rule":
        assessment["reglas"].pop()
    elif invalid_condition == "low_frequency":
        assessment["datos_tecnicos"]["frecuencia_muestreo_hz"] = 250
    elif invalid_condition == "short_capture":
        assessment["datos_tecnicos"]["cantidad_muestras"] = MUESTRAS_CAPTURA_SENSOR
    elif invalid_condition == "adc_units":
        assessment["datos_tecnicos"]["unidad"] = "ADC"
    elif invalid_condition == "quality_not_apt":
        assessment["calidad_senal"] = "NO EVALUADA"
    else:
        assessment["parametros_no_evaluables"] = ["RC-ECG-004: falta evidencia"]

    rendered = _render_preventive_assessment(ecg_client, assessment)

    selected = [card for card in rendered["cards"] if card["selected"]]
    assert [(card["nivel"], card["color"]) for card in selected] == [
        ("NO_EVALUABLE", "GRIS")
    ]
    assert rendered["nivel"].startswith("NO EVALUABLE")


def test_evaluacion_preventiva_no_infiere_calidad_ni_alerta_desde_muestras_ruidosas():
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[0, 4095, 0, 4095],
        unidad="ADC",
    )

    evaluacion = evaluar_captura_preventiva(datos)

    assert evaluacion.nivel == "NO_EVALUABLE"
    assert evaluacion.calidad_senal == "NO EVALUADA O INSUFICIENTE"
    assert evaluacion.valores_medidos == {
        "RC-ECG-002.frecuencia_muestreo_hz": 250.0,
    }
    assert evaluacion.reglas[1].estado == "NO_CUMPLE"
    assert "250 Hz" in evaluacion.reglas[1].motivo
    assert evaluacion.reglas[8].estado == "NO_EVALUABLE"
    assert any("Ruido eléctrico e interferencias" in item for item in evaluacion.advertencias_tecnicas)


def _indices_picos_sinteticos(muestras):
    return [
        indice
        for indice in range(1, len(muestras) - 1)
        if muestras[indice] >= 0.8
        and muestras[indice] >= muestras[indice - 1]
        and muestras[indice] >= muestras[indice + 1]
    ]


def test_simulador_permite_configurar_frecuencia_y_duracion():
    datos = generar_datos_ecg(frecuencia_cardiaca_bpm=60, duracion_segundos=5)
    picos = _indices_picos_sinteticos(datos["muestras"])

    assert len(datos["muestras"]) == 1250
    assert DatosECG.model_validate(datos).frecuencia_muestreo_hz == 250
    assert len(picos) >= 4
    assert [right - left for left, right in zip(picos, picos[1:])] == [250] * (len(picos) - 1)


def test_senal_muy_corta_solo_se_valida_como_formato_tecnico():
    datos = generar_datos_ecg(duracion_segundos=0.004)

    assert len(datos["muestras"]) == 1
    assert DatosECG.model_validate(datos).muestras == datos["muestras"]


def test_simulador_genera_intervalos_regulares_e_irregulares_reproducibles():
    regular = generar_datos_ecg(ritmo="regular")
    irregular = generar_datos_ecg(ritmo="irregular", semilla=17)
    irregular_repetido = generar_datos_ecg(ritmo="irregular", semilla=17)
    rr_regular = [
        right - left
        for left, right in zip(
            _indices_picos_sinteticos(regular["muestras"]),
            _indices_picos_sinteticos(regular["muestras"])[1:],
        )
    ]
    picos_irregulares = _indices_picos_sinteticos(irregular["muestras"])
    rr_irregular = [right - left for left, right in zip(picos_irregulares, picos_irregulares[1:])]

    assert irregular == irregular_repetido
    assert len(set(rr_regular)) == 1
    assert len(set(rr_irregular)) > 1
    assert max(rr_irregular) - min(rr_irregular) >= 20


def test_simulador_admite_ruido_artefacto_y_onda_p_no_visible_solo_como_datos():
    limpia = generar_datos_ecg()
    ruidosa = generar_datos_ecg(ruido_amplitud=0.02, semilla=9)
    artefacto = generar_datos_ecg(artefacto_sintetico=True)
    sin_onda_p = generar_datos_ecg(onda_p_visible=False)

    assert ruidosa == generar_datos_ecg(ruido_amplitud=0.02, semilla=9)
    assert ruidosa["muestras"] != generar_datos_ecg(ruido_amplitud=0.02, semilla=10)["muestras"]
    assert artefacto["muestras"] != limpia["muestras"]
    assert sin_onda_p["muestras"] != limpia["muestras"]
    for datos in (ruidosa, artefacto, sin_onda_p):
        assert DatosECG.model_validate(datos)
        assert all(math.isfinite(muestra) for muestra in datos["muestras"])


@pytest.mark.parametrize(
    "parametros",
    [
        {"frecuencia_cardiaca_bpm": 0},
        {"frecuencia_cardiaca_bpm": 75.5},
        {"duracion_segundos": 0},
        {"duracion_segundos": float("nan")},
        {"ritmo": "sinusoidal"},
        {"ruido_amplitud": -0.1},
        {"ruido_amplitud": float("inf")},
        {"semilla": 1.5},
    ],
)
def test_simulador_rechaza_parametros_invalidos(parametros):
    with pytest.raises(ValueError):
        generar_datos_ecg(**parametros)


@pytest.mark.parametrize(
    "datos",
    [
        {},
        {"frecuencia_muestreo_hz": 0, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": -1, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250.5, "muestras": [0.1], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": ["0.1"], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [float("nan")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [float("inf")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [-float("inf")], "unidad": "mV"},
        {"frecuencia_muestreo_hz": 250, "muestras": [0.1], "unidad": "V"},
    ],
)
def test_datos_ecg_rechaza_campos_y_valores_invalidos(datos):
    with pytest.raises(ValidationError):
        DatosECG.model_validate(datos)


def test_datos_ecg_conserva_adc_y_muestras_mV_OUT_independientes():
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[2048, 2050, 2047],
        unidad="ADC",
        muestras_mV_OUT=[1651, 1652, 1650],
        calibracion_adc=_metadatos_calibracion_adc_sinteticos(),
    )

    assert datos.muestras == [2048, 2050, 2047]
    assert datos.muestras_mV_OUT == [1651, 1652, 1650]
    assert datos.calibracion_adc.vref_efuse_mv == 1093


def test_datos_ecg_marca_mV_OUT_no_confiable_sin_atribuir_autenticidad():
    datos = DatosECG(
        frecuencia_muestreo_hz=250,
        muestras=[2048],
        unidad="ADC",
        muestras_mV_OUT=[1651],
        estado_mV_OUT="NO_CONFIABLE",
    )

    assert datos.muestras == [2048]
    assert datos.muestras_mV_OUT == [1651]
    assert datos.estado_mV_OUT == "NO_CONFIABLE"


def test_datos_ecg_rechaza_estado_mV_OUT_verificado_declarado_por_cliente():
    datos = {
        "frecuencia_muestreo_hz": 250,
        "muestras": [2048],
        "unidad": "ADC",
        "muestras_mV_OUT": [1651],
        "estado_mV_OUT": "VERIFICADA",
    }

    with pytest.raises(ValidationError):
        DatosECG.model_validate(datos)


@pytest.mark.parametrize(
    "cambios",
    [
        {"muestras_mV_OUT": [1000]},
        {"muestras_mV_OUT": [1000, 1001]},
        {
            "muestras_mV_OUT": [1000, 1001],
            "calibracion_adc": _metadatos_calibracion_adc_sinteticos("ERROR"),
        },
        {
            "muestras_mV_OUT": [1000, 1001],
            "calibracion_adc": {
                **_metadatos_calibracion_adc_sinteticos(),
                "vref_efuse_mv": 1100,
            },
        },
        {
            "muestras_mV_OUT": [1000, 1001],
            "calibracion_adc": {
                **_metadatos_calibracion_adc_sinteticos(),
                "chip_model": "ESP32-S3",
            },
        },
    ],
)
def test_datos_ecg_rechaza_mV_OUT_sin_evidencia_calibracion_coherente(cambios):
    with pytest.raises(ValidationError):
        DatosECG(
            frecuencia_muestreo_hz=250,
            muestras=[2048, 2050],
            unidad="ADC",
            **cambios,
        )


def test_datos_ecg_rechaza_estado_calibrado_sin_muestras_mV_OUT():
    with pytest.raises(ValidationError):
        DatosECG(
            frecuencia_muestreo_hz=250,
            muestras=[2048],
            unidad="ADC",
            calibracion_adc=_metadatos_calibracion_adc_sinteticos(),
        )


def test_datos_ecg_rechaza_muestras_mV_OUT_no_enteras_o_negativas():
    for muestras_mv_out in ([1000.5], [-1], [True]):
        with pytest.raises(ValidationError):
            DatosECG(
                frecuencia_muestreo_hz=250,
                muestras=[2048],
                unidad="ADC",
                muestras_mV_OUT=muestras_mv_out,
                calibracion_adc=_metadatos_calibracion_adc_sinteticos(),
            )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("episodio_id", 0),
        ("episodio_id", -1),
        ("dispositivo_id", 0),
        ("dispositivo_id", -1),
    ],
)
def test_entrada_ecg_rechaza_identificadores_no_positivos(campo, valor):
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    entrada[campo] = valor

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


@pytest.mark.parametrize(
    "campo",
    ["episodio_id", "dispositivo_id", "origen", "data"],
)
def test_entrada_ecg_rechaza_campos_obligatorios_ausentes(campo):
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    del entrada[campo]

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


def test_entrada_ecg_usa_solo_los_campos_del_contrato():
    assert set(EntradaECG.model_fields) == {
        "episodio_id",
        "dispositivo_id",
        "origen",
        "data",
    }


def test_entrada_ecg_rechaza_origen_invalido():
    entrada = {
        "episodio_id": 1,
        "dispositivo_id": 1,
        "origen": "MANUAL",
        "data": generar_datos_ecg(),
    }

    with pytest.raises(ValidationError):
        EntradaECG.model_validate(entrada)


def test_guardar_resultado_valido(ecg_client, test_engine, ecg_references):
    entrada = _entrada_valida(ecg_references)

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 201
    respuesta = response.json()
    assert respuesta["mensaje"] == "Resultado guardado correctamente"
    assert isinstance(respuesta["resultado_id"], int)

    with Session(test_engine) as session:
        resultado = session.exec(select(ResultadoModulo)).one()

    assert resultado.id == respuesta["resultado_id"]
    assert resultado.modulo == "ecg"
    assert resultado.episodio_id == ecg_references["episodio_id"]
    assert resultado.dispositivo_id == ecg_references["dispositivo_id"]
    assert json.loads(resultado.data_json) == entrada["data"]


def test_post_resultados_recibe_captura_sensor_y_persiste(ecg_client, test_engine, ecg_references):
    entrada = _entrada_sensor_valida(ecg_references)

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 201
    assert response.json()["mensaje"] == "Resultado guardado correctamente"
    with Session(test_engine) as session:
        resultado = session.exec(select(ResultadoModulo)).one()
    assert resultado.modulo == "ecg"
    assert resultado.dispositivo_id == ecg_references["dispositivo_id"]
    assert json.loads(resultado.data_json) == entrada["data"]


def test_post_get_mV_OUT_preserva_adc_y_capturas_historicas(
    ecg_client, test_engine, ecg_references
):
    historica = _entrada_sensor_valida(
        ecg_references,
        adquisicion_id="00000000-0000-4000-8000-000000000088",
    )
    entrada = _entrada_sensor_valida(
        ecg_references,
        adquisicion_id="00000000-0000-4000-8000-000000000089",
    )
    entrada["data"]["muestras_mV_OUT"] = [
        1651 + (index % 4) for index in range(MUESTRAS_CAPTURA_SENSOR)
    ]
    entrada["data"]["calibracion_adc"] = _metadatos_calibracion_adc_sinteticos()

    guardado_historico = ecg_client.post(RUTA, json=historica)
    guardado_calibrado = ecg_client.post(RUTA, json=entrada)
    consulta = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}")

    assert guardado_historico.status_code == 201
    assert guardado_calibrado.status_code == 201
    assert consulta.status_code == 200
    resultados = consulta.json()["resultados"]
    assert len(resultados) == 2
    assert resultados[0]["data"]["muestras"] == historica["data"]["muestras"]
    assert "muestras_mV_OUT" not in resultados[0]["data"]
    assert resultados[1]["data"]["muestras"] == entrada["data"]["muestras"]
    assert resultados[1]["data"]["muestras_mV_OUT"] == entrada["data"]["muestras_mV_OUT"]
    assert resultados[1]["data"]["estado_mV_OUT"] == "NO_CONFIABLE"
    assert resultados[1]["data"]["calibracion_adc"]["estado"] == "NO_CONFIABLE"
    assert "no puede verificar" in resultados[1]["data"]["calibracion_adc"]["error"]
    assert resultados[1]["evaluacion_preventiva"]["nivel"] == "NO_EVALUABLE"
    with Session(test_engine) as session:
        persistidos = session.exec(select(ResultadoModulo)).all()
    historico_guardado = json.loads(persistidos[0].data_json)
    assert historico_guardado == historica["data"]
    datos_mv_guardados = json.loads(persistidos[1].data_json)
    assert datos_mv_guardados["muestras"] == entrada["data"]["muestras"]
    assert datos_mv_guardados["estado_mV_OUT"] == "NO_CONFIABLE"
    assert datos_mv_guardados["calibracion_adc"]["estado"] == "NO_CONFIABLE"


def test_get_degrada_calibracion_historica_sin_modificar_el_registro(
    ecg_client, test_engine, ecg_references
):
    entrada = _entrada_sensor_valida(
        ecg_references,
        adquisicion_id="00000000-0000-4000-8000-000000000091",
    )
    entrada["data"]["muestras_mV_OUT"] = [
        1651 + (index % 4) for index in range(MUESTRAS_CAPTURA_SENSOR)
    ]
    entrada["data"]["calibracion_adc"] = _metadatos_calibracion_adc_sinteticos()
    json_historico = json.dumps(entrada["data"])
    with Session(test_engine) as session:
        resultado = ResultadoModulo(
            episodio_id=ecg_references["episodio_id"],
            dispositivo_id=ecg_references["dispositivo_id"],
            modulo="ecg",
            data_json=json_historico,
        )
        session.add(resultado)
        session.commit()

    consulta = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}")

    assert consulta.status_code == 200
    data = consulta.json()["resultados"][0]["data"]
    assert data["muestras"] == entrada["data"]["muestras"]
    assert data["muestras_mV_OUT"] == entrada["data"]["muestras_mV_OUT"]
    assert data["estado_mV_OUT"] == "NO_CONFIABLE"
    assert data["calibracion_adc"]["estado"] == "NO_CONFIABLE"
    with Session(test_engine) as session:
        persistido = session.exec(select(ResultadoModulo)).one()
    assert persistido.data_json == json_historico

    reintento = ecg_client.post(RUTA, json=entrada)

    assert reintento.status_code == 200
    with Session(test_engine) as session:
        persistido = session.exec(select(ResultadoModulo)).one()
    assert persistido.data_json == json_historico


def test_frontend_muestra_ADC_y_no_grafica_mV_OUT_no_confiable(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "sensor-mode")

    assert "ADC original" in result["unitLabel"]
    assert "no confiable" in result["unitLabel"]
    assert "mV_OUT calibrados" not in result["description"]


def test_post_get_conserva_adc_y_error_calibracion_sin_mV_OUT(
    ecg_client, ecg_references
):
    entrada = _entrada_sensor_valida(
        ecg_references,
        adquisicion_id="00000000-0000-4000-8000-000000000090",
    )
    entrada["data"]["calibracion_adc"] = _metadatos_calibracion_adc_sinteticos(
        "ERROR"
    )

    guardado = ecg_client.post(RUTA, json=entrada)
    consulta = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}")

    assert guardado.status_code == 201
    result = consulta.json()["resultados"][0]
    assert result["data"]["muestras"] == entrada["data"]["muestras"]
    assert result["data"]["calibracion_adc"]["estado"] == "ERROR"
    assert result["data"]["estado_mV_OUT"] == "NO_EVALUABLE"
    assert "muestras_mV_OUT" not in result["data"]
    assert result["evaluacion_preventiva"]["nivel"] == "NO_EVALUABLE"


@pytest.mark.parametrize(
    "mutacion",
    [
        lambda entrada: entrada["data"].update(frecuencia_muestreo_hz=200),
        lambda entrada: entrada["data"].update(unidad="mV"),
        lambda entrada: entrada["data"].update(muestras=entrada["data"]["muestras"][:-1]),
        lambda entrada: entrada["data"].update(adquisicion_id=None),
        lambda entrada: entrada.update(dispositivo_id=0),
        lambda entrada: entrada["data"]["muestras"].__setitem__(0, 4096),
        lambda entrada: entrada["data"]["muestras"].__setitem__(0, -1),
        lambda entrada: entrada["data"]["muestras"].append(2048),
        lambda entrada: entrada.pop("dispositivo_id"),
    ],
)
def test_post_resultados_rechaza_capturas_fisicas_invalidas(ecg_client, ecg_references, mutacion):
    entrada = _entrada_sensor_valida(ecg_references)
    mutacion(entrada)

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 422


def test_esp32_reintento_idempotente_conserva_capturas_historicas(
    ecg_client, ecg_references, test_engine
):
    historica = _entrada_valida(ecg_references)
    historica["data"]["adquisicion_id"] = "00000000-0000-4000-8000-000000000088"
    sensor = _entrada_sensor_valida(ecg_references)

    primera_historica = ecg_client.post(RUTA, json=historica)
    primera_captura = ecg_client.post(RUTA, json=sensor)
    reintento = ecg_client.post(RUTA, json=sensor)
    consulta = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}")

    assert primera_historica.status_code == 201
    assert primera_captura.status_code == 201
    assert reintento.status_code == 200
    assert reintento.json()["resultado_id"] == primera_captura.json()["resultado_id"]
    assert consulta.status_code == 200
    resultados = consulta.json()["resultados"]
    assert len(resultados) == 2
    assert resultados[0]["id"] == primera_historica.json()["resultado_id"]
    assert resultados[1]["id"] == primera_captura.json()["resultado_id"]
    assert resultados[1]["data"]["adquisicion_id"] == sensor["data"]["adquisicion_id"]
    with Session(test_engine) as session:
        assert len(session.exec(select(ResultadoModulo)).all()) == 2


def test_esp32_no_asocia_captura_a_un_dispositivo_distinto(
    ecg_client, ecg_references, test_engine
):
    with Session(test_engine) as session:
        dispositivo = Dispositivo(
            codigo="ECG-002",
            nombre="Otro dispositivo ECG",
            tipo="ECG",
        )
        session.add(dispositivo)
        session.commit()
        session.refresh(dispositivo)
        dispositivo_id = dispositivo.id

    entrada = _entrada_sensor_valida(ecg_references)
    entrada["dispositivo_id"] = dispositivo_id

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 422
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_esp32_asocia_captura_al_episodio_y_rechaza_episodio_inexistente(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_sensor_valida(ecg_references)
    entrada["episodio_id"] = 999999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_esp32_rechaza_episodio_cerrado(ecg_client, ecg_references, test_engine):
    with Session(test_engine) as session:
        episodio = session.get(EpisodioAtencion, ecg_references["episodio_id"])
        episodio.estado = "FINALIZADO"
        session.add(episodio)
        session.commit()

    response = ecg_client.post(
        RUTA,
        json=_entrada_sensor_valida(ecg_references),
    )

    assert response.status_code == 409
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_swagger_registra_un_unico_post_ecg_para_guardar_resultados(ecg_app):
    paths = ecg_app.openapi()["paths"]
    post_ecg_paths = [
        path for path, methods in paths.items()
        if path.startswith("/api/v1/ecg/") and "post" in methods
    ]

    assert post_ecg_paths == [RUTA]


def test_simulador_genera_identidad_nueva_aunque_las_muestras_sean_iguales(ecg_client):
    first = ecg_client.get("/api/v1/ecg/simulador/captura")
    second = ecg_client.get("/api/v1/ecg/simulador/captura")

    assert first.status_code == second.status_code == 200
    first_data = first.json()
    second_data = second.json()
    first_id = UUID(first_data.pop("adquisicion_id"))
    second_id = UUID(second_data.pop("adquisicion_id"))

    assert first_id != second_id
    assert first_id.version == second_id.version == 4
    assert first_data == second_data


def test_post_reintentado_con_misma_adquisicion_reutiliza_resultado(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada["data"]["adquisicion_id"] = "00000000-0000-4000-8000-000000000012"

    first = ecg_client.post(RUTA, json=entrada)
    retry = ecg_client.post(RUTA, json=entrada)

    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["resultado_id"] == first.json()["resultado_id"]
    with Session(test_engine) as session:
        results = session.exec(select(ResultadoModulo)).all()
    assert len(results) == 1
    assert results[0].id == first.json()["resultado_id"]


def test_adquisiciones_distintas_con_mismas_muestras_crean_resultados_independientes(
    ecg_client, ecg_references
):
    first_entry = _entrada_valida(ecg_references)
    first_entry["data"]["adquisicion_id"] = "00000000-0000-4000-8000-000000000021"
    second_entry = {
        **first_entry,
        "data": {
            **first_entry["data"],
            "adquisicion_id": "00000000-0000-4000-8000-000000000022",
        },
    }

    first = ecg_client.post(RUTA, json=first_entry)
    second = ecg_client.post(RUTA, json=second_entry)
    results = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}").json()["resultados"]

    assert first.status_code == second.status_code == 201
    assert first.json()["resultado_id"] != second.json()["resultado_id"]
    assert len(results) == 2
    assert results[0]["data"]["muestras"] == results[1]["data"]["muestras"]
    assert results[0]["data"]["adquisicion_id"] != results[1]["data"]["adquisicion_id"]


def test_reutilizar_adquisicion_con_datos_distintos_devuelve_conflicto(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada["data"]["adquisicion_id"] = "00000000-0000-4000-8000-000000000031"
    first = ecg_client.post(RUTA, json=entrada)
    entrada["data"]["muestras"][0] += 1

    conflict = ecg_client.post(RUTA, json=entrada)

    assert first.status_code == 201
    assert conflict.status_code == 409
    with Session(test_engine) as session:
        results = session.exec(select(ResultadoModulo)).all()
    assert len(results) == 1


def test_post_episodio_inexistente_devuelve_404_sin_persistir(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada["episodio_id"] = 999999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404
    assert response.json()["detail"] == "El episodio no existe"
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_post_rechaza_entrada_invalida_con_422(ecg_client, ecg_references):
    entrada = _entrada_valida(ecg_references)
    entrada["data"]["unidad"] = "V"

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "campo_id",
    ["episodio_id", "dispositivo_id"],
)
def test_post_referencia_inexistente_devuelve_404(
    campo_id, ecg_client, ecg_references, test_engine
):
    entrada = _entrada_valida(ecg_references)
    entrada[campo_id] = 999

    response = ecg_client.post(RUTA, json=entrada)

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_get_resultados_del_episodio(ecg_client, ecg_references):
    entrada = _entrada_valida(ecg_references)
    guardado = ecg_client.post(RUTA, json=entrada)

    response = ecg_client.get(
        f"{RUTA}/{ecg_references['episodio_id']}"
    )

    assert guardado.status_code == 201
    assert response.status_code == 200
    respuesta = RespuestaConsulta.model_validate(response.json())
    assert respuesta.episodio_id == ecg_references["episodio_id"]
    assert respuesta.modulo == "ecg"
    assert len(respuesta.resultados) == 1
    assert respuesta.resultados[0].id == guardado.json()["resultado_id"]
    assert respuesta.resultados[0].data.model_dump(exclude_none=True) == entrada["data"]
    assert "adquisicion_id" not in response.json()["resultados"][0]["data"]
    evaluacion = respuesta.resultados[0].evaluacion_preventiva
    assert evaluacion.nivel == "NO_EVALUABLE"
    assert evaluacion.color == "GRIS"
    assert evaluacion.datos_tecnicos.cantidad_muestras == len(entrada["data"]["muestras"])


def test_get_resultados_agrega_evaluacion_sin_modificar_datos_persistidos(
    ecg_client, ecg_references, test_engine
):
    entrada = _entrada_sensor_valida(ecg_references)
    guardado = ecg_client.post(RUTA, json=entrada)

    response = ecg_client.get(f"{RUTA}/{ecg_references['episodio_id']}")

    assert response.status_code == 200
    result = response.json()["resultados"][0]
    assert result["id"] == guardado.json()["resultado_id"]
    assert result["evaluacion_preventiva"]["nivel"] == "NO_EVALUABLE"
    assert result["evaluacion_preventiva"]["datos_tecnicos"] == {
        "frecuencia_muestreo_hz": 250,
        "cantidad_muestras": MUESTRAS_CAPTURA_SENSOR,
        "unidad": "ADC",
    }
    with Session(test_engine) as session:
        stored = session.exec(select(ResultadoModulo)).one()
    assert json.loads(stored.data_json) == entrada["data"]


def test_flujo_sensor_adquisicion_guardado_consulta_y_confirmacion_frontend(
    ecg_client, ecg_references
):
    entrada = _entrada_sensor_valida(
        ecg_references,
        adquisicion_id="00000000-0000-4000-8000-000000000123",
    )

    guardado = ecg_client.post(RUTA, json=entrada)
    assert guardado.status_code == 201
    resultado_id = guardado.json()["resultado_id"]

    consulta = ecg_client.get(
        f"{RUTA}/{ecg_references['episodio_id']}"
    )
    assert consulta.status_code == 200
    body = consulta.json()
    assert body["episodio_id"] == ecg_references["episodio_id"]
    assert body["modulo"] == "ecg"
    assert isinstance(body["resultados"], list)
    result = next(item for item in body["resultados"] if item["id"] == resultado_id)
    assert result["data"]["adquisicion_id"] == entrada["data"]["adquisicion_id"]
    assert result["data"]["frecuencia_muestreo_hz"] == 250
    assert result["data"]["unidad"] == "ADC"
    assert len(result["data"]["muestras"]) == MUESTRAS_CAPTURA_SENSOR
    assert result["evaluacion_preventiva"]["nivel"] == "NO_EVALUABLE"
    assert result["evaluacion_preventiva"]["color"] == "GRIS"
    assert len(result["evaluacion_preventiva"]["reglas"]) == 9
    assert result["evaluacion_preventiva"]["reglas"][1]["estado"] == "NO_CUMPLE"
    assert all(
        rule["estado"] == "NO_EVALUABLE"
        for rule in result["evaluacion_preventiva"]["reglas"][2:]
    )

    frontend = _run_sensor_persistence_poll(
        ecg_client, body, entrada["data"]["adquisicion_id"]
    )
    assert frontend["queryCount"] == 1
    assert frontend["confirmed"] is True, frontend
    assert frontend["resultId"] == resultado_id
    assert f"#{resultado_id}" in frontend["guardStatus"]
    assert frontend["errorVisible"] is False


def test_consulta_ecg_invalida_no_confirma_captura(
    ecg_client, ecg_references
):
    invalid_response = {
        "episodio_id": ecg_references["episodio_id"],
        "modulo": "ecg",
        "resultados": {"id": 12},
    }

    frontend = _run_sensor_persistence_poll(
        ecg_client,
        invalid_response,
        "00000000-0000-4000-8000-000000000124",
    )

    assert frontend["queryCount"] == 1
    assert frontend["confirmed"] is False
    assert frontend["guardStatus"] == "No se confirmó un resultado guardado."
    assert frontend["errorVisible"] is True
    assert "resultados incompatibles" in frontend["error"]


def test_get_episodio_existente_sin_resultados_devuelve_lista_vacia(
    ecg_client, ecg_references
):
    response = ecg_client.get(
        f"{RUTA}/{ecg_references['episodio_id']}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "episodio_id": ecg_references["episodio_id"],
        "modulo": "ecg",
        "resultados": [],
    }


def test_get_episodio_inexistente_devuelve_404(ecg_client):
    response = ecg_client.get(f"{RUTA}/999")

    assert response.status_code == 404


@pytest.mark.parametrize("episodio_id", [0, -1])
def test_get_episodio_no_positivo_devuelve_422(ecg_client, episodio_id):
    response = ecg_client.get(f"{RUTA}/{episodio_id}")

    assert response.status_code == 422


def test_pantalla_ecg_disponible_desde_router_principal(ecg_client):
    response = ecg_client.get("/api/v1/ecg/pantalla")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Recorrido educativo de captura ECG" in response.text
    assert "/api/v1/ecg/frontend.js" in response.text


def test_pantalla_ecg_muestra_el_contexto_sin_datos_de_simulacion(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text

    assert 'id="episodio-contexto"' in html
    assert 'id="episodio-inicio"' in html
    assert "episodio real" in html
    assert "simulación" not in html.lower()


def test_pantalla_ecg_expone_no_evaluable_y_avisos_permanentes(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    assert 'id="evaluacion-preventiva"' in html
    assert 'id="evaluacion-nivel"' in html
    assert 'id="evaluacion-parametros-pendientes"' in html
    assert 'id="evaluacion-advertencias"' in html
    assert "NO EVALUABLE" in html
    assert "una sola señal del AD8232" in html
    assert "12 derivaciones" in html
    assert "eje eléctrico frontal" in html
    assert "Ruido eléctrico e interferencias" in html
    assert "no equivale a una alerta clínica" in html
    assert "renderPreventiveAssessment(result)" in javascript
    assert html.count('class="assessment-state"') == 4
    assert 'assessment?.nivel' in javascript
    assert 'assessment?.color' in javascript
    assert 'assessment.motivo.trim()' in javascript


def test_grafica_ecg_mantiene_ventana_deslizante_de_diez_segundos(ecg_client):
    result = _simulate_live_signal_buffer(ecg_client)

    assert result["capacity"] == result["size"] == 2500
    assert result["lastSequence"] - result["firstSequence"] == 2499
    assert result["pathCommands"] == 2500
    assert result["firstSequence"] == 500
    assert result["lastSequence"] == 2999
    assert result["offsetOneSecondLater"] < result["offsetAtSample"]
    assert result["frameOffset"] != result["nextFrameOffset"]
    assert float(result["frameOffset"].split("(")[1].split()[0]) == 620
    assert float(result["nextFrameOffset"].split("(")[1].split()[0]) < 620
    assert result["uniqueSequences"] == 2500
    assert result["gapCount"] == 1
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    assert 'id="tiempo-total"' in html
    assert ">10 s</text>" in html
    assert 'id="trazo-senal" d=""' in html
    assert 'clip-path="url(#recorte-senal)"' in html
    assert 'id="ecg-subdivisiones"' in html
    assert 'id="ecg-divisiones-principales"' in html


def test_grafica_ecg_mapea_las_2500_muestras_a_ventana_nominal_de_diez_segundos(
    ecg_client,
):
    result = _simulate_live_signal_buffer(ecg_client)

    assert result["nominalWindowSeconds"] == 10
    assert result["completePath"].startswith("M-547.78,160.00")
    assert result["completePath"].endswith("L0.00,20.00")


def test_grafica_ecg_centra_la_linea_base_y_autoajusta_solo_la_presentacion(ecg_client):
    result = _simulate_live_signal_buffer(ecg_client)
    expected_points = []
    for index, sample in enumerate([0, 2048, 4095]):
        x = (index - 2) * (548 / 2500)
        y = 90 - ((sample - 2047.5) / 2047.5) * 70
        expected_points.append(
            f"{'M' if index == 0 else 'L'}{x:.2f},{y:.2f}"
        )

    assert result["probePath"] == " ".join(expected_points)
    assert result["centeredScale"] == {"baseline": 2050, "amplitude": 250}
    assert "línea base visual ADC: 2047.5" in result["saturationStatus"]
    assert "No se dispone de mV_OUT calibrados." in result["saturationStatus"]
    assert "Muestras en rieles 0/4095: 1/1" in result["saturationStatus"]
    assert result["axisLabels"] == [
        "4095", "2047.5", "0", "ADC (cuentas; autoescala visual, no mV)"
    ]
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    assert 'id="escala-vertical"' not in html
    assert "Completa:" not in html
    assert "Reducida:" not in html
    assert "no representa papel ECG calibrado" in html
    assert "mV_OUT (tensión a la salida del AD8232)" in html
    assert "Esto no es mV_ECG" in html
    assert "eFuse Vref verificada" in html
    assert result["calibratedAxis"] == (
        "mV_OUT (tensión calibrada a la salida del AD8232; autoescala)"
    )
    assert "No representa mV_ECG" in result["calibratedStatus"]


def test_grafica_ecg_no_conecta_muestras_tras_desconexion(ecg_client):
    result = _simulate_live_signal_buffer(ecg_client)

    assert result["gapMoves"] == 2


def test_grafica_ecg_conserva_todas_las_muestras_dentro_de_la_ventana(ecg_client):
    result = _simulate_live_signal_buffer(ecg_client)

    assert result["retainedSequences"] == list(range(500, 3000))


def test_pantalla_transversal_no_solicita_paciente_sin_contexto(ecg_client):
    html_response = ecg_client.get("/api/v1/ecg/circuito/pantalla")

    assert html_response.status_code == 200
    assert html_response.headers["cache-control"] == "no-store"
    assert 'name="tipo_circuito" value="GUARDIA"' in html_response.text
    assert 'name="tipo_circuito" value="COMPLETO"' in html_response.text
    assert 'id="paciente-id-entrada"' not in html_response.text
    assert 'id="crear-episodio" type="button" disabled' in html_response.text
    assert "no define un mecanismo para compartirlo entre pantallas" in html_response.text
    assert 'id="abrir-ecg"' in html_response.text
    assert "Si esta pantalla recibe un `episodio_id` real en la URL" in html_response.text
    assert 'id="episodio-activo"' in html_response.text
    assert 'id="episodio-id"' in html_response.text
    assert 'id="episodio-circuito"' in html_response.text
    assert 'id="episodio-inicio"' in html_response.text

def test_api_pacientes_devuelve_registros_reales_para_modo_prueba(client):
    created = client.post(
        "/api/v1/pacientes",
        json={
            "dni": "30987654",
            "nombre": "Paciente",
            "apellido": "Prueba temporal",
            "fecha_nacimiento": "1990-04-12",
        },
    )
    assert created.status_code == 201

    response = client.get("/api/v1/pacientes")

    assert response.status_code == 200
    patient = next(item for item in response.json() if item["id"] == created.json()["id"])
    assert patient["nombre"] == "Paciente"
    assert patient["apellido"] == "Prueba temporal"
    assert patient["dni"] == "30987654"


@pytest.mark.parametrize("tipo_circuito", ["GUARDIA", "COMPLETO"])
def test_app_principal_crea_episodio_con_circuito_admitido(
    client, test_engine, tipo_circuito
):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="12345678",
            nombre="Paciente",
            apellido="Prueba",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        paciente_id = paciente.id

    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": tipo_circuito},
    )

    assert response.status_code == 201
    assert response.json()["tipo_circuito"] == tipo_circuito
    assert response.json()["paciente_id"] == paciente_id


@pytest.mark.parametrize(
    "tipo_circuito",
    ["", "DESCONOCIDO", "TRIAJE_PREVENTIVO"],
)
def test_app_principal_rechaza_circuito_no_admitido_sin_crear_episodio(
    client, test_engine, tipo_circuito
):
    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": 1, "tipo_circuito": tipo_circuito},
    )

    assert response.status_code == 422
    with Session(test_engine) as session:
        assert session.exec(select(EpisodioAtencion)).all() == []


def test_app_principal_rechaza_paciente_inexistente(client, test_engine):
    response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": 999999, "tipo_circuito": "COMPLETO"},
    )

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(EpisodioAtencion)).all() == []


@pytest.mark.parametrize("tipo_circuito", ["GUARDIA", "COMPLETO"])
def test_app_principal_persiste_y_consulta_ecg_simulado(
    client, test_engine, tipo_circuito
):
    patient_created = client.post(
        "/api/v1/pacientes",
        json={
            "dni": "87654321",
            "nombre": "Paciente",
            "apellido": "Prueba ECG",
            "fecha_nacimiento": "2000-01-01",
        },
    )
    assert patient_created.status_code == 201
    patient_list = client.get("/api/v1/pacientes")
    assert patient_list.status_code == 200
    paciente_id = patient_created.json()["id"]
    patient = next(item for item in patient_list.json() if item["id"] == paciente_id)
    assert patient["dni"] == "87654321"

    episodio_response = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": tipo_circuito},
    )
    assert episodio_response.status_code == 201
    episodio_id = episodio_response.json()["id"]
    episode_check = client.get(f"/api/v1/episodios/{episodio_id}")
    assert episode_check.status_code == 200
    assert episode_check.json()["paciente_id"] == paciente_id
    assert episode_check.json()["tipo_circuito"] == tipo_circuito

    dispositivo_response = client.post(
        "/api/v1/dispositivos",
        json={"codigo": "ECG-001", "nombre": "ECG de prueba", "tipo": "ECG"},
    )
    assert dispositivo_response.status_code == 201
    dispositivos = client.get("/api/v1/dispositivos")
    assert dispositivos.status_code == 200
    dispositivo = next(item for item in dispositivos.json() if item["codigo"] == "ECG-001")
    assert dispositivo["tipo"] == "ECG"
    assert dispositivo["activo"] is True
    assert dispositivo["estado"] == "DISPONIBLE"

    captura = client.get("/api/v1/ecg/simulador/captura").json()
    entrada = {
        "episodio_id": episodio_id,
        "dispositivo_id": dispositivo["id"],
        "origen": "SIMULADOR",
        "data": captura,
    }
    guardado = client.post("/api/v1/ecg/resultados", json=entrada)

    assert guardado.status_code == 201
    resultado_id = guardado.json()["resultado_id"]
    consulta = client.get(f"/api/v1/ecg/resultados/{episodio_id}")
    assert consulta.status_code == 200
    resultado = next(
        item for item in consulta.json()["resultados"] if item["id"] == resultado_id
    )
    assert consulta.json()["episodio_id"] == episodio_id
    assert resultado["data"] == captura

    with Session(test_engine) as session:
        persistido = session.exec(select(ResultadoModulo)).one()
    assert persistido.modulo == "ecg"
    assert persistido.episodio_id == episodio_id
    assert persistido.dispositivo_id == dispositivo["id"]
    assert json.loads(persistido.data_json) == captura


@pytest.mark.parametrize("campo_id", ["episodio_id", "dispositivo_id"])
def test_app_principal_no_persiste_resultado_con_referencia_inexistente(
    client, test_engine, campo_id
):
    with Session(test_engine) as session:
        paciente = Paciente(
            dni="11223344",
            nombre="Paciente",
            apellido="Prueba error",
            fecha_nacimiento=date(2000, 1, 1),
        )
        session.add(paciente)
        session.commit()
        session.refresh(paciente)
        paciente_id = paciente.id

    episodio = client.post(
        "/api/v1/episodios",
        json={"paciente_id": paciente_id, "tipo_circuito": "COMPLETO"},
    ).json()
    dispositivo = client.post(
        "/api/v1/dispositivos",
        json={"codigo": "ECG-001", "nombre": "ECG de prueba", "tipo": "ECG"},
    ).json()
    entrada = {
        "episodio_id": episodio["id"],
        "dispositivo_id": dispositivo["id"],
        "origen": "SIMULADOR",
        "data": generar_datos_ecg(),
    }
    entrada[campo_id] = 999999

    response = client.post("/api/v1/ecg/resultados", json=entrada)

    assert response.status_code == 404
    with Session(test_engine) as session:
        assert session.exec(select(ResultadoModulo)).all() == []


def test_frontend_usa_solo_adquisicion_fisica_y_guarda_al_confirmar_api(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    response = ecg_client.get("/api/v1/ecg/frontend.js")
    javascript = response.text

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'id="iniciar-ecg"' in html
    assert ">Iniciar ECG</button>" in html
    assert 'id="esp32-url"' not in html
    assert 'id="estado-dispositivo"' in html
    assert 'id="estado-captura"' in html
    assert 'id="trazo-senal"' in html
    assert 'id="capturas-historicas"' in html
    assert "/configurar" in javascript
    assert "/iniciar" in javascript
    assert "/api/ecg" in javascript
    assert "${API}/ecg/conexion" in javascript
    assert '"DESCONECTADO"' in javascript
    assert '"CONECTANDO"' in javascript
    assert '"CONECTADO"' in javascript
    assert '"ERROR"' in javascript
    assert "la captura aún no está confirmada" in javascript
    assert "${API}/ecg/resultados/${episodioActivo.id}" in javascript
    assert "Resultado guardado: la API confirmó" in javascript
    assert "adquisicion_id" in javascript
    assert 'device.codigo === "ECG-001"' in javascript
    assert 'dispositivo_id: String(dispositivoEcg.id)' in javascript
    assert "Number.isSafeInteger(device.id)" in javascript
    assert "origen: \"SIMULADOR\"" not in javascript
    assert "/ecg/simulador/captura" not in javascript
    assert "SIMULACIÓN" not in html
    assert "simulación" not in html.lower()
    assert 'id="modo-simulacion"' not in html
    assert 'id="guardar-resultado"' not in html
    assert "finalizar sin guardar" not in html.lower()
    assert 'id="finalizar-simulacion"' not in html
    assert 'id="finalizar-ecg"' not in html
    results_url = "`${API}/ecg/resultados/${episodioActivo.id}`"
    results_query = javascript[javascript.index(results_url):]
    assert 'method: "POST"' not in results_query[:200]
    assert "Math.sin" not in javascript


def test_descubrimiento_ecg_devuelve_dispositivos_mdns(ecg_client, monkeypatch):
    class DiscoveryStub:
        def dispositivos(self):
            return [{"codigo": "ECG-001", "base_url": "http://192.168.0.42:80"}]

    monkeypatch.setattr(
        "app.modules.ecg.router.get_ecg_discovery",
        lambda: DiscoveryStub(),
    )

    response = ecg_client.get("/api/v1/ecg/conexion")

    assert response.status_code == 200
    assert response.json() == {
        "dispositivos": [
            {"codigo": "ECG-001", "base_url": "http://192.168.0.42:80"}
        ]
    }


def test_descubrimiento_ecg_informa_lista_vacia(ecg_client, monkeypatch):
    class DiscoveryStub:
        def dispositivos(self):
            return []

    monkeypatch.setattr(
        "app.modules.ecg.router.get_ecg_discovery",
        lambda: DiscoveryStub(),
    )

    response = ecg_client.get("/api/v1/ecg/conexion")

    assert response.status_code == 200
    assert response.json() == {"dispositivos": []}


def test_frontend_conserva_navegacion_y_grafica_sin_controles_legacy(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    step_ids = ["paso-preparacion", "paso-electrodos", "paso-captura", "paso-resumen"]
    assert [html.index(f'id="{step_id}"') for step_id in step_ids] == sorted(
        html.index(f'id="{step_id}"') for step_id in step_ids
    )
    html_ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(html_ids) == len(set(html_ids))
    selectors = re.findall(r'app\.querySelector\("#([^"]+)"\)', javascript)
    assert set(selectors) <= set(html_ids)
    assert 'id="paso-siguiente"' in html
    assert '<dl id="resumen-tecnico"' in html
    assert 'src="/api/v1/ecg/frontend.js"' in html
    assert "muestras: shown" not in javascript
    assert "origen: \"SIMULADOR\"" not in javascript


def test_frontend_ecg_muestra_fecha_del_episodio_si_la_api_la_devuelve(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    assert 'id="episodio-inicio"' in html
    assert 'episode.iniciado_en' in javascript
    assert 'dateStyle: "short"' in javascript
    assert 'timeStyle: "short"' in javascript


def test_captura_simulada_reutiliza_esquema_ecg(ecg_client):
    response = ecg_client.get("/api/v1/ecg/simulador/captura")

    assert response.status_code == 200
    first_capture = response.json()
    second_capture = ecg_client.get("/api/v1/ecg/simulador/captura").json()

    assert DatosECG.model_validate(first_capture)
    assert first_capture["adquisicion_id"] != second_capture["adquisicion_id"]
    assert {key: first_capture[key] for key in generar_datos_ecg()} == generar_datos_ecg()



def test_pantalla_ecg_mantiene_la_secuencia_de_navegacion(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    step_ids = ["paso-preparacion", "paso-electrodos", "paso-captura", "paso-resumen"]
    assert [html.index(f'id="{step_id}"') for step_id in step_ids] == sorted(
        html.index(f'id="{step_id}"') for step_id in step_ids
    )
    html_ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(html_ids) == len(set(html_ids))
    selectors = re.findall(r'app\.querySelector\("#([^"]+)"\)', javascript)
    assert set(selectors) <= set(html_ids)
    assert html.count('id="paso-siguiente"') == 1
    assert all(f'#{step_id}' in javascript for step_id in step_ids)
    assert javascript.count('app.querySelector("#paso-siguiente").addEventListener("click"') == 1
    assert "showStep(currentStep + 1)" in javascript
    assert 'app.querySelector("#iniciar-ecg").addEventListener("click"' in javascript
    assert 'id="paso-guardar"' not in html
    assert 'id="paciente-seleccionado"' not in html
    assert 'id="paso-siguiente"' in html
    assert '<dl id="resumen-tecnico"' in html
    assert 'id="cantidad-final"' in html
    assert 'id="frecuencia-final"' in html
    assert 'id="unidad-final"' in html
    assert 'id="trazo-senal"' in html
    assert "capturaActual.muestras" in javascript
    assert "adquisicion_id" in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert 'src="/api/v1/ecg/frontend.js"' in html
