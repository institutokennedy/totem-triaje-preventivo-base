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
  let isSaving = false;
  let stopRequested = false;
  let flowFinalized = false;
  let captureRevision = 0;
  let savedRevision = null;
  let savedResultId = null;
  const episodioParam = new URLSearchParams(window.location.search).get("episodio_id");
  const episodeId = episodioParam && /^[1-9]\d*$/.test(episodioParam)
    ? Number(episodioParam)
    : null;
  let deviceId = null;
  let referencesLoaded = false;
  let referencesLoading = false;
  let uncertainSave = null;

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
    app.querySelector("#paso-anterior").disabled = index === 0 || isCapturing || isSaving;
    const next = app.querySelector("#paso-siguiente");
    next.hidden = index === stepPanels.length - 1;
    next.disabled = isCapturing || isSaving || (index === 1 && !app.querySelector("#aceptar-referencia-electrodos").checked) || (index === 2 && capture === null);
    updateConfirmationControls();
    if (index === 3 && !referencesLoaded && !referencesLoading) loadPersistenceReferences();
    if (!preserveError) app.querySelector("#error").hidden = true;
  }

  function updateConfirmationControls() {
    const button = app.querySelector("#guardar-captura");
    button.disabled = !capture || episodeId === null || isSaving || savedRevision === captureRevision;
    button.textContent = uncertainSave
      ? "Verificar guardado"
      : "Guardar en la base de datos";
  }

  function setPersistenceStatus(message) {
    app.querySelector("#estado-persistencia").textContent = message;
  }

  async function loadPersistenceReferences() {
    if (referencesLoading) return;
    referencesLoading = true;
    referencesLoaded = false;
    deviceId = null;
    if (episodeId === null || !Number.isSafeInteger(episodeId)) {
      setPersistenceStatus("No se recibió un episodio activo válido. Volvé al tótem e ingresá al ECG desde el episodio actual.");
      referencesLoading = false;
      return;
    }
    setPersistenceStatus("Verificando el episodio activo y buscando el dispositivo ECG registrado…");
    try {
      const [episode, devices] = await Promise.all([
        requestJson(`${API}/episodios/${episodeId}`, { headers: { Accept: "application/json" } }),
        requestJson(`${API}/dispositivos`, { headers: { Accept: "application/json" } }),
      ]);
      if (!episode || episode.id !== episodeId) {
        throw new Error("La API no confirmó el episodio activo recibido.");
      }
      const ecgDevice = devices.find((device) =>
        device.codigo === "ECG-001" && device.tipo === "ECG" && device.activo === true &&
        Number.isSafeInteger(device.id) && device.id > 0
      );
      if (!ecgDevice) {
        throw new Error("No se encontró un dispositivo ECG-001 activo en la API.");
      }
      deviceId = ecgDevice.id;
      referencesLoaded = true;
      setPersistenceStatus(`Episodio ${episodeId} y dispositivo ECG-001 verificados. La captura se enviará solo al guardar.`);
    } catch (error) {
      setPersistenceStatus(`No se pudo validar el episodio o resolver el dispositivo ECG: ${error.message} Podés reintentar con el botón de guardado; todavía no se envió la captura.`);
    } finally {
      referencesLoading = false;
    }
  }

  function matchingNewResult(results, baselineIds, expectedData) {
    return results.find((result) =>
      !baselineIds.has(result.id) && JSON.stringify(result.data) === JSON.stringify(expectedData)
    );
  }

  function markCaptureSaved(resultId, verifiedByQuery = false) {
    savedRevision = captureRevision;
    savedResultId = resultId;
    uncertainSave = null;
    app.querySelector("#estado-guardado").textContent = verifiedByQuery
      ? `La consulta confirmó que la captura quedó guardada (resultado ${resultId}).`
      : `Captura guardada correctamente (resultado ${resultId}).`;
    updateConfirmationControls();
  }

  async function verifyUncertainSave() {
    if (!uncertainSave || isSaving) return;
    isSaving = true;
    updateConfirmationControls();
    try {
      const result = await requestJson(`${API}/ecg/resultados/${uncertainSave.episodeId}`, {
        headers: { Accept: "application/json" },
      });
      const saved = matchingNewResult(result.resultados, uncertainSave.baselineIds, uncertainSave.data);
      if (saved) {
        captureRevision = uncertainSave.revision;
        markCaptureSaved(saved.id, true);
      } else {
        uncertainSave = null;
        app.querySelector("#estado-guardado").textContent = "La consulta no encontró esta captura entre los resultados nuevos. Podés reintentar la confirmación.";
      }
    } catch (error) {
      app.querySelector("#estado-guardado").textContent = `No se pudo verificar todavía si se guardó: ${error.message}. Reintentá la consulta antes de enviar otra vez.`;
    } finally {
      isSaving = false;
      updateConfirmationControls();
    }
  }

  async function confirmCapture() {
    if (!capture || isSaving) return;
    if (uncertainSave) return verifyUncertainSave();

    isSaving = true;
    app.querySelector("#estado-guardado").textContent = "Verificando referencias antes de guardar…";
    updateConfirmationControls();
    let baselineIds;
    try {
      if (!referencesLoaded) await loadPersistenceReferences();
      if (!referencesLoaded || episodeId === null || deviceId === null) {
        app.querySelector("#estado-guardado").textContent = "No se envió la captura: falta validar el episodio activo o el dispositivo ECG. Corregí el contexto y reintentá.";
        return;
      }
      const before = await requestJson(`${API}/ecg/resultados/${episodeId}`, {
        headers: { Accept: "application/json" },
      });
      baselineIds = new Set(before.resultados.map((result) => result.id));
      const saved = await requestJson(`${API}/ecg/resultados`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          episodio_id: episodeId,
          dispositivo_id: deviceId,
          origen: "SIMULADOR",
          data: capture,
        }),
      });
      if (!Number.isInteger(saved.resultado_id) || saved.resultado_id <= 0) {
        throw new Error("La API no devolvió la confirmación esperada del guardado.");
      }
      markCaptureSaved(saved.resultado_id);
    } catch (error) {
      if (!baselineIds) {
        app.querySelector("#estado-guardado").textContent = `No se pudo validar el episodio; no se confirmó ningún guardado: ${error.message}`;
        return;
      }
      try {
        const after = await requestJson(`${API}/ecg/resultados/${episodeId}`, {
          headers: { Accept: "application/json" },
        });
        const saved = matchingNewResult(after.resultados, baselineIds, capture);
        if (saved) {
          markCaptureSaved(saved.id, true);
        } else {
          app.querySelector("#estado-guardado").textContent = `No se confirmó el guardado (${error.message}). No se encontró un resultado nuevo; podés reintentar.`;
        }
      } catch (verificationError) {
        uncertainSave = { episodeId, baselineIds, data: capture, revision: captureRevision };
        app.querySelector("#estado-guardado").textContent = `La respuesta del guardado y su verificación no estuvieron disponibles (${verificationError.message}). Para evitar duplicados, usá el mismo botón para verificar antes de reenviar.`;
      }
    } finally {
      isSaving = false;
      updateConfirmationControls();
    }
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
    if (isCapturing || isSaving || flowFinalized) return;
    captureRevision += 1;
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
    app.querySelector("#estado-finalizacion").textContent = savedRevision === captureRevision && savedResultId
      ? `La captura actual quedó guardada como resultado ${savedResultId}.`
      : "La captura actual finalizó sin guardarse.";
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
  app.querySelector("#repetir-ecg").addEventListener("click", startSimulation);
  app.querySelector("#finalizar-ecg").addEventListener("click", finishCaptureFlow);
  app.querySelector("#guardar-captura").addEventListener("click", confirmCapture);
  showStep(0);
})();
