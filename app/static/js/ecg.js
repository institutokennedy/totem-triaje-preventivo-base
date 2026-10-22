(() => {
  "use strict";

  const API = "/api/v1";
  const app = document.getElementById("ecg-app");
  const stepPanels = [
    "#paso-preparacion",
    "#paso-electrodos",
    "#paso-captura",
    "#paso-resumen",
  ].map((selector) => app.querySelector(selector));
  const stepNames = [
    "Limpieza de la piel",
    "Colocación de electrodos",
    "Generación del ECG simulado",
    "Resumen de captura",
  ];
  const navItems = [...app.querySelectorAll(".steps li")];
  let currentStep = 0;
  let capture = null;
  let isCapturing = false;
  let stopRequested = false;
  let flowFinalized = false;

  function showStep(index, preserveError = false) {
    if (flowFinalized) return;
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
    next.disabled = isCapturing || (index === 1 && !app.querySelector("#aceptar-referencia-electrodos").checked) || (index === 2 && capture === null);
    if (!preserveError) app.querySelector("#error").hidden = true;
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

  function hasTechnicalInterference(samples) {
    return samples.length > 1 && samples.every((sample) => sample === samples[0]);
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
    if (isCapturing || flowFinalized) return;
    capture = null;
    stopRequested = false;
    app.querySelector("#interferencia-panel").hidden = true;
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
      if (hasTechnicalInterference(capture.muestras)) {
        capture = null;
        app.querySelector("#estado-simulacion").textContent = "La señal presenta una condición técnica para repetir o finalizar; no se conserva en el resumen.";
        app.querySelector("#interferencia-panel").hidden = false;
      }
    } catch (error) {
      app.querySelector("#estado-simulacion").textContent = "No se completó la simulación.";
      reportError(error);
    } finally {
      isCapturing = false;
      app.querySelector("#iniciar-simulacion").disabled = false;
      app.querySelector("#detener-simulacion").hidden = true;
      showStep(currentStep, true);
    }
  }

  function finishCaptureFlow() {
    flowFinalized = true;
    stepPanels.forEach((panel) => { panel.hidden = true; });
    app.querySelector(".steps").hidden = true;
    app.querySelector("#captura-finalizada").hidden = false;
    app.querySelector("#paso-actual").textContent = "Captura finalizada";
    app.querySelector("nav").hidden = true;
  }

  app.querySelector("#paso-anterior").addEventListener("click", () => {
    if (currentStep > 0 && !isCapturing) showStep(currentStep - 1);
  });
  app.querySelector("#paso-siguiente").addEventListener("click", () => {
    if (currentStep < stepPanels.length - 1 && !(currentStep === 2 && !capture)) showStep(currentStep + 1);
  });
  app.querySelector("#aceptar-referencia-electrodos").addEventListener("change", (event) => {
    app.querySelector("#paso-siguiente").disabled = !event.target.checked;
    if (currentStep === 1) showStep(1);
  });
  app.querySelector("#iniciar-simulacion").addEventListener("click", startSimulation);
  app.querySelector("#detener-simulacion").addEventListener("click", () => {
    stopRequested = true;
    app.querySelector("#estado-simulacion").textContent = "Deteniendo la presentación de muestras…";
  });
  app.querySelector("#repetir-simulacion").addEventListener("click", () => {
    capture = null;
    showStep(2);
    startSimulation();
  });
  app.querySelector("#finalizar-simulacion").addEventListener("click", finishCaptureFlow);
  app.querySelector("#repetir-ecg").addEventListener("click", startSimulation);
  app.querySelector("#finalizar-ecg").addEventListener("click", finishCaptureFlow);
  showStep(0);
})();
