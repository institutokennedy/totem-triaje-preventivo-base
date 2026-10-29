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
from app.modules.ecg.schemas import DatosECG, EntradaECG, RespuestaConsulta
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
            codigo="001",
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
  replaceChildren() {}
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
      id: 23, codigo: "001", tipo: "ECG", activo: true, estado: "DISPONIBLE",
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
  document: { getElementById: (id) => elements.get(id) || null },
  Error,
  Intl,
  URLSearchParams,
  window: {
    location: { search: "?episodio_id=42" },
    setTimeout: (callback) => queueMicrotask(callback),
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
    if (calls.some((call) => call.url === "/api/v1/dispositivos")) return;
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


def test_pantalla_ecg_delimita_contextos_hu09_y_hu14(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text

    assert "no se recibió una clasificación roja válida" in html
    assert "no se recibió un episodio del circuito completo" in html
    assert "esta pantalla no declara que el flujo HU-09 esté habilitado" in html


def test_pantalla_transversal_no_solicita_paciente_sin_contexto(ecg_client):
    html_response = ecg_client.get("/api/v1/ecg/circuito/pantalla")
    js_response = ecg_client.get("/api/v1/ecg/circuito/frontend.js")

    assert html_response.status_code == 200
    assert js_response.status_code == 200
    assert html_response.headers["cache-control"] == "no-store"
    assert 'name="tipo_circuito" value="GUARDIA"' in html_response.text
    assert 'name="tipo_circuito" value="COMPLETO"' in html_response.text
    assert 'id="paciente-id-entrada"' not in html_response.text
    assert 'id="crear-episodio" type="button" disabled' in html_response.text
    assert "no define un mecanismo para compartirlo entre pantallas" in html_response.text
    assert 'id="abrir-ecg"' in html_response.text
    assert "Si esta pantalla recibe un `episodio_id` real en la URL" in html_response.text
    assert 'new URLSearchParams(window.location.search).get("episodio_id")' in js_response.text
    assert '`/api/v1/episodios/${episodeId}`' in js_response.text
    assert 'openEcg.href = `/api/v1/ecg/pantalla?episodio_id=${encodeURIComponent(episode.id)}`' in js_response.text
    assert 'app.querySelector("#episodio-inicio").textContent = formatEpisodeDate(episode.iniciado_en)' in js_response.text
    assert "No se selecciona ningún paciente automáticamente." in js_response.text
    assert 'radio.addEventListener("change"' in js_response.text
    html_ids = re.findall(r'\bid="([^"]+)"', html_response.text)
    selectors = re.findall(r'app\.querySelector\("#([^\"]+)"\)', js_response.text)
    assert len(html_ids) == len(set(html_ids))
    assert set(selectors) <= set(html_ids)


def test_pantalla_temporal_prueba_hu03_y_ecg(client):
    page = client.get("/api/v1/ecg/circuito/prueba")
    script = client.get("/api/v1/ecg/circuito/frontend.js")

    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert page.headers["cache-control"] == "no-store"
    assert "Herramienta temporal de prueba" in page.text
    assert 'data-mode="prueba"' in page.text
    assert 'src="/api/v1/ecg/circuito/frontend.js"' in page.text
    assert 'value="">Cargando pacientes…' in page.text
    assert 'name="tipo_circuito" value="GUARDIA"' in page.text
    assert 'name="tipo_circuito" value="COMPLETO"' in page.text
    assert script.status_code == 200
    assert 'API + "/pacientes"' in script.text
    assert 'new Option("Seleccioná un paciente existente…", "")' in script.text
    assert 'API + "/episodios"' in script.text
    assert 'API + "/episodios/" + created.id' in script.text
    assert "checked.paciente_id !== patient.id" in script.text
    assert 'root.querySelector("#seccion-ecg-prueba").hidden = false' in script.text
    assert 'API + "/dispositivos"' in script.text
    assert 'API + "/ecg/simulador/captura"' in script.text
    assert 'API + "/ecg/resultados"' in script.text
    assert 'API + "/ecg/resultados/" + episode.id' in script.text
    assert "localStorage" not in script.text
    assert "sessionStorage" not in script.text
    normal_flow, test_flow = script.text.split("function startTestMode(root)", maxsplit=1)
    assert 'new URLSearchParams(window.location.search).get("episodio_id")' in normal_flow
    assert "URLSearchParams" not in test_flow


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


def test_pantallas_y_javascript_ecg_accesibles_desde_app_principal(client):
    pantalla_ecg = client.get("/api/v1/ecg/pantalla")
    pantalla_circuito = client.get("/api/v1/ecg/circuito/pantalla")
    javascript_ecg = client.get("/api/v1/ecg/frontend.js")
    javascript_circuito = client.get("/api/v1/ecg/circuito/frontend.js")

    assert pantalla_ecg.status_code == 200
    assert "text/html" in pantalla_ecg.headers["content-type"]
    assert 'src="/api/v1/ecg/frontend.js"' in pantalla_ecg.text
    assert pantalla_circuito.status_code == 200
    assert "text/html" in pantalla_circuito.headers["content-type"]
    assert 'src="/api/v1/ecg/circuito/frontend.js"' in pantalla_circuito.text
    assert javascript_ecg.status_code == 200
    assert "javascript" in javascript_ecg.headers["content-type"]
    assert javascript_circuito.status_code == 200
    assert "javascript" in javascript_circuito.headers["content-type"]


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
        json={"codigo": "001", "nombre": "ECG de prueba", "tipo": "ECG"},
    )
    assert dispositivo_response.status_code == 201
    dispositivos = client.get("/api/v1/dispositivos")
    assert dispositivos.status_code == 200
    dispositivo = next(item for item in dispositivos.json() if item["codigo"] == "001")
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
        json={"codigo": "001", "nombre": "ECG de prueba", "tipo": "ECG"},
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


def test_frontend_ecg_prepara_persistencia_con_contexto_real(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    response = ecg_client.get("/api/v1/ecg/frontend.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "/ecg/simulador/captura" in response.text
    assert "new URLSearchParams(window.location.search)" in response.text
    assert "${API}/episodios/${episodioId}" in response.text
    assert "${API}/dispositivos" in response.text
    assert 'device.codigo === "001"' in response.text
    assert 'device.tipo === "ECG"' in response.text
    assert "device.activo === true" in response.text
    assert 'origen: "SIMULADOR"' in response.text
    assert 'method: "POST"' in response.text
    assert "${API}/ecg/resultados/${episodioActivo.id}" in response.text
    assert '<section id="persistencia-panel"' in html
    assert '<button id="guardar-resultado" type="button" disabled>' in html
    assert 'saveButton.hidden = false' in response.text
    assert 'saveButton.disabled = !(hasEpisode && dispositivoEcg && capture' in response.text
    assert "paciente_id" not in response.text
    assert "no se declara completado el flujo rojo HU-09" in response.text
    assert "Prueba técnica HU-14" in response.text
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text


def test_frontend_ecg_reconcilia_error_antes_de_habilitar_reintento(ecg_client):
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    assert "async function reconcileUnconfirmedSave(error)" in javascript
    assert "await obtenerResultadosPersistidos()" in javascript
    assert "const match = results.find((result) => sameAcquisition(result.data, capture))" in javascript
    assert "canSubmitCapture = false" in javascript
    assert "canSubmitCapture = true" in javascript
    assert "El POST falló: ${postError}" in javascript
    assert "Además, no se pudo consultar el estado" in javascript
    assert "mostrarResultados(results)" not in javascript
    assert "results.some((result) => result.id === savedResultId && sameAcquisition(result.data, capture))" in javascript
    assert "if (!episodioActivo || !Number.isSafeInteger(episodioActivo.id) || episodioActivo.id <= 0" in javascript
    assert "paciente_id" not in javascript


def test_frontend_confirmar_envia_contexto_y_verifica_persistencia(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "confirm-success")

    posts = [
        call for call in result["calls"]
        if call["url"] == RUTA and call["method"] == "POST"
    ]
    assert len(posts) == 1
    assert posts[0]["body"]["episodio_id"] == 42
    assert posts[0]["body"]["dispositivo_id"] == 23
    assert posts[0]["body"]["origen"] == "SIMULADOR"
    assert posts[0]["body"]["data"] == {
        "adquisicion_id": "00000000-0000-4000-8000-000000000001",
        "frecuencia_muestreo_hz": 250,
        "muestras": [0.1, 0.3],
        "unidad": "mV",
    }
    assert result["resultsRequests"] == 2
    assert len(result["records"]) == 1
    assert "guardado del resultado" in result["status"]
    assert result["errorVisible"] is False


def test_frontend_repetir_no_guarda_ni_borra_historicos_o_duplica(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "repeat-no-save")

    assert result["postsAfterRepeat"] == 0
    assert result["recordsAfterRepeat"] == 1
    assert result["postRequests"] == 1
    assert len(result["records"]) == 2
    assert result["records"][0]["data"]["adquisicion_id"] != result["records"][1]["data"]["adquisicion_id"]
    assert result["records"][0]["data"]["muestras"] == result["records"][1]["data"]["muestras"]
    assert "guardado del resultado" in result["status"]


def test_frontend_muestra_error_post_y_reconcilia_antes_de_reintentar(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "post-422")

    assert result["postRequests"] == 1
    assert result["resultsRequests"] == 2
    assert result["records"] == []
    assert result["errorVisible"] is True
    assert "422" in result["error"]
    assert "muestras para el episodio" in result["status"]
    assert result["confirmDisabled"] is False


def test_frontend_no_envia_post_si_falla_consulta_previa(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "preflight-query-fails")

    assert result["resultsRequests"] == 1
    assert result["postRequests"] == 0
    assert result["errorVisible"] is True
    assert "503" in result["error"]
    assert "POST porque no se pudo comprobar" in result["status"]


def test_frontend_bloquea_repetir_hasta_resolver_guardado_incierto(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "uncertain-query-fails")

    assert result["repeatDisabledWhileUncertain"] is True
    assert result["simulatorCountAfterBlockedRepeat"] == result["simulatorCountWhileUncertain"]
    assert result["errorVisibleWhileUncertain"] is True
    assert "503" in result["errorWhileUncertain"]
    assert result["postRequests"] == 1
    assert result["resultsRequests"] == 3
    assert len(result["records"]) == 1
    assert " #100." in result["status"]


def test_frontend_muestra_error_de_validacion_del_simulador(ecg_client):
    result = _run_frontend_interaction_test(ecg_client, "invalid-simulator")

    assert result["postRequests"] == 0
    assert result["records"] == []
    assert result["errorVisible"] is True
    assert "datos ECG" in result["error"]


def test_frontend_ecg_muestra_fecha_del_episodio_si_la_api_la_devuelve(ecg_client):
    html = ecg_client.get("/api/v1/ecg/pantalla").text
    javascript = ecg_client.get("/api/v1/ecg/frontend.js").text

    assert 'id="episodio-inicio"' in html
    assert 'episode.iniciado_en' in javascript
    assert 'dateStyle: "short"' in javascript
    assert 'timeStyle: "short"' in javascript


def test_herramienta_temporal_muestra_estado_y_requisitos_del_guardado(ecg_client):
    html = ecg_client.get("/api/v1/ecg/circuito/prueba").text
    javascript = ecg_client.get("/api/v1/ecg/circuito/frontend.js").text

    assert '<button id="guardar-ecg-prueba" type="button" hidden disabled>' in html
    assert 'id="disponibilidad-guardado-prueba"' in html
    assert 'saveButton.addEventListener("click", saveCapture)' in javascript
    assert 'item.tipo === "ECG"' in javascript
    assert 'item.estado === "DISPONIBLE"' in javascript
    assert 'item.activo === true' in javascript
    assert 'Number.isSafeInteger(item.id) && item.id > 0' in javascript
    assert 'item.codigo === "001"' in javascript
    assert 'id="episodio-inicio-prueba"' in html
    assert 'episode.iniciado_en' in javascript
    assert 'dispositivo_id: device.id' in javascript
    assert "No se encontró un dispositivo ECG activo y disponible" in javascript
    assert "falta un episodio verificado" in javascript
    assert "falta un dispositivo ECG activo y disponible" in javascript
    assert "falta generar la señal simulada" in javascript
    assert "Consultando resultados existentes antes de enviar la captura" in javascript
    assert 'API + "/ecg/resultados"' in javascript
    assert 'API + "/ecg/resultados/" + episode.id' in javascript
    assert "Guardado confirmado y verificado por la API" in javascript
    assert "paciente_id: episode.paciente_id" not in javascript


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
    assert 'app.querySelector("#repetir-ecg").addEventListener("click", startSimulation)' in javascript
    assert 'app.querySelector("#finalizar-ecg").addEventListener("click", finishCaptureFlow)' in javascript
    assert 'app.querySelector("#finalizar-simulacion").addEventListener("click", finishCaptureFlow)' in javascript
    assert 'id="paso-guardar"' not in html
    assert 'id="paciente-seleccionado"' not in html
    assert 'id="paso-siguiente"' in html
    assert '<dl id="resumen-tecnico"' in html
    assert 'id="cantidad-final"' in html
    assert 'id="frecuencia-final"' in html
    assert 'id="unidad-final"' in html
    assert 'app.querySelector("#cantidad-final").textContent = String(capture.muestras.length)' in javascript
    assert 'app.querySelector("#frecuencia-final").textContent = `${capture.frecuencia_muestreo_hz} Hz`' in javascript
    assert 'app.querySelector("#unidad-final").textContent = capture.unidad' in javascript
    assert "muestras: shown" in javascript
    assert "${API}/ecg/resultados" in javascript
    assert "origen: \"SIMULADOR\"" in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert "No se guardó ningún resultado." in html
    assert 'src="/api/v1/ecg/frontend.js"' in html
