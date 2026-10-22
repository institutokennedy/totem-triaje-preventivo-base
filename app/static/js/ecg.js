(() => {
  "use strict";

  const API = "/api/v1";
  const DEVICE_CODE = "ECG-001";
  const app = document.getElementById("ecg-app");
  const stepPanels = [
    "#paso-preparacion",
    "#paso-electrodos",
    "#paso-conexiones",
    "#paso-captura",
    "#paso-resumen",
    "#paso-guardar",
  ].map((selector) => app.querySelector(selector));
  const stepNames = [
    "Preparación del paciente",
    "Electrodos",
    "Conexiones",
    "Captura ECG simulada",
    "Resumen de captura",
    "Asociar a un episodio y guardar (opcional)",
  ];
  const navItems = [...app.querySelectorAll(".steps li")];
  let currentStep = 0;
  let capture = null;
  let device = null;
  let episodeId = null;
  let isCapturing = false;
  let stopRequested = false;

  function showStep(index) {
    currentStep = index;
    app.dataset.step = String(index);
    stepPanels.forEach((panel, panelIndex) => { panel.hidden = panelIndex !== index; });
    navItems.forEach((item, itemIndex) => {
      if (itemIndex === index) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    app.querySelector("#paso-actual").textContent = `Paso ${index + 1} de ${stepPanels.length}: ${stepNames[index]}`;
    app.querySelector("#paso-anterior").disabled = index === 0 || isCapturing;
    const next = app.querySelector("#paso-siguiente");
    next.hidden = index === stepPanels.length - 1;
    next.disabled = isCapturing || (index === 3 && capture === null);
    app.querySelector("#guardar-resultado").disabled = capture === null;
    app.querySelector("#error").hidden = true;
  }

  function reportError(error) {
    const message = error instanceof Error ? error.message : "Ocurrió un error técnico inesperado.";
    app.querySelector("#mensaje-error").textContent = message;
    app.querySelector("#error").hidden = false;
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`;
      throw new Error(`${detail} (${response.status}).`);
    }
    return body;
  }

  function delay(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function drawSignal(samples) {
    const maxMagnitude = Math.max(...samples.map((sample) => Math.abs(sample)), 1);
    const points = samples.map((sample, index) => {
      const x = 28 + index * (584 / Math.max(samples.length - 1, 1));
      const y = 90 - (sample / maxMagnitude) * 68;
      return `${x},${y}`;
    });
    app.querySelector("#trazo-senal").setAttribute("points", points.join(" "));
  }

  function clearSignal() {
    app.querySelector("#muestras-vistas").replaceChildren();
    app.querySelector("#trazo-senal").setAttribute("points", "");
    app.querySelector("#cantidad-en-curso").textContent = "0";
    app.querySelector("#cantidad-final").textContent = "—";
    app.querySelector("#frecuencia-final").textContent = "—";
    app.querySelector("#unidad-final").textContent = "—";
  }

  async function presentSamples(data) {
    const list = app.querySelector("#muestras-vistas");
    list.replaceChildren();
    const shown = [];
    for (const sample of data.muestras) {
      await delay(220);
      if (stopRequested) break;
      shown.push(sample);
      const item = document.createElement("li");
      item.className = "sample";
      item.textContent = String(sample);
      list.append(item);
      app.querySelector("#cantidad-en-curso").textContent = String(shown.length);
      drawSignal(shown);
    }
    if (shown.length === 0) {
      throw new Error("La simulación se detuvo antes de presentar una muestra. Iniciá una nueva simulación.");
    }
    capture = {
      frecuencia_muestreo_hz: data.frecuencia_muestreo_hz,
      muestras: shown,
      unidad: data.unidad,
    };
    app.querySelector("#cantidad-final").textContent = String(shown.length);
    app.querySelector("#frecuencia-final").textContent = `${capture.frecuencia_muestreo_hz} Hz`;
    app.querySelector("#unidad-final").textContent = capture.unidad;
    const state = app.querySelector("#estado-simulacion");
    state.textContent = stopRequested
      ? `Simulación detenida. Se conservaron ${shown.length} muestra(s) ficticia(s).`
      : `Simulación finalizada. Se presentaron ${shown.length} muestras ficticias.`;
    app.querySelector("#detener-simulacion").hidden = true;
  }

  async function startSimulation() {
    if (isCapturing) return;
    capture = null;
    stopRequested = false;
    clearSignal();
    isCapturing = true;
    app.querySelector("#iniciar-simulacion").disabled = true;
    app.querySelector("#detener-simulacion").hidden = false;
    app.querySelector("#estado-simulacion").textContent = "Solicitando lote de muestras ficticias al simulador Python…";
    showStep(currentStep);
    try {
      const data = await requestJson(`${API}/ecg/simulador/captura`, {
        headers: { Accept: "application/json" },
      });
      if (
        !Number.isInteger(data.frecuencia_muestreo_hz) || data.frecuencia_muestreo_hz <= 0 ||
        !Array.isArray(data.muestras) || data.muestras.length === 0 ||
        !data.muestras.every((sample) => typeof sample === "number" && Number.isFinite(sample)) ||
        !["mV", "ADC"].includes(data.unidad)
      ) {
        throw new Error("La respuesta del simulador no cumple el esquema técnico de datos ECG.");
      }
      await presentSamples(data);
    } catch (error) {
      app.querySelector("#estado-simulacion").textContent = "No se completó la simulación.";
      reportError(error);
    } finally {
      isCapturing = false;
      app.querySelector("#iniciar-simulacion").disabled = false;
      app.querySelector("#detener-simulacion").hidden = true;
      showStep(currentStep);
    }
  }

  async function resolvePersistenceReferences() {
    const id = Number(app.querySelector("#episodio-id").value);
    if (!Number.isInteger(id) || id <= 0) {
      throw new Error("Para guardar, ingresá un episodio_id entero mayor que cero.");
    }
    const [episode, devices] = await Promise.all([
      requestJson(`${API}/episodios/${id}`, { headers: { Accept: "application/json" } }),
      requestJson(`${API}/dispositivos`, { headers: { Accept: "application/json" } }),
    ]);
    if (episode.id !== id || episode.estado !== "INICIADO") {
      throw new Error("El episodio debe existir y estar en estado INICIADO para guardar el resultado.");
    }
    device = devices.find((item) => item.codigo === DEVICE_CODE && item.tipo === "ECG" && item.activo === true);
    if (!device || !Number.isInteger(device.id) || device.id <= 0) {
      throw new Error(`No se encontró un dispositivo ECG activo con código ${DEVICE_CODE}. No se creó ningún dispositivo.`);
    }
    episodeId = id;
  }

  async function saveCapture() {
    if (!capture) {
      reportError(new Error("Primero completá una simulación."));
      return;
    }
    const status = app.querySelector("#estado-guardado");
    status.textContent = "Verificando episodio y dispositivo existentes…";
    app.querySelector("#guardar-resultado").disabled = true;
    try {
      await resolvePersistenceReferences();
      const result = await requestJson(`${API}/ecg/resultados`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          episodio_id: episodeId,
          dispositivo_id: device.id,
          origen: "SIMULADOR",
          data: capture,
        }),
      });
      status.textContent = `Resultado ${result.resultado_id} guardado para el episodio ${episodeId}. Origen: SIMULADOR.`;
      app.querySelector("#consultar-resultados").hidden = false;
    } catch (error) {
      status.textContent = "No se guardó ningún resultado.";
      reportError(error);
    } finally {
      app.querySelector("#guardar-resultado").disabled = false;
    }
  }

  async function consultResults() {
    if (!episodeId) {
      app.querySelector("#estado-consulta").textContent = "Guardá primero o ingresá un episodio en la etapa opcional.";
      return;
    }
    const status = app.querySelector("#estado-consulta");
    const list = app.querySelector("#resultados-guardados");
    list.replaceChildren();
    try {
      const result = await requestJson(`${API}/ecg/resultados/${episodeId}`, {
        headers: { Accept: "application/json" },
      });
      status.textContent = result.resultados.length
        ? `${result.resultados.length} resultado(s) persistido(s) para el episodio ${episodeId}.`
        : `No hay resultados ECG guardados para el episodio ${episodeId}.`;
      for (const saved of result.resultados) {
        const item = document.createElement("li");
        item.textContent = `Resultado ${saved.id}: ${saved.data.muestras.length} muestras, ${saved.data.frecuencia_muestreo_hz} Hz, ${saved.data.unidad}.`;
        list.append(item);
      }
    } catch (error) {
      status.textContent = "No se pudieron consultar los resultados.";
      reportError(error);
    }
  }

  app.querySelector("#paso-anterior").addEventListener("click", () => {
    if (currentStep > 0 && !isCapturing) showStep(currentStep - 1);
  });
  app.querySelector("#paso-siguiente").addEventListener("click", () => {
    if (currentStep < stepPanels.length - 1 && !(currentStep === 3 && !capture)) showStep(currentStep + 1);
  });
  app.querySelector("#iniciar-simulacion").addEventListener("click", startSimulation);
  app.querySelector("#detener-simulacion").addEventListener("click", () => {
    stopRequested = true;
    app.querySelector("#estado-simulacion").textContent = "Deteniendo la presentación de muestras…";
  });
  app.querySelector("#repetir-simulacion").addEventListener("click", () => {
    capture = null;
    showStep(3);
    startSimulation();
  });
  app.querySelector("#guardar-resultado").addEventListener("click", saveCapture);
  app.querySelector("#consultar-resultados").addEventListener("click", consultResults);
  showStep(0);
})();
