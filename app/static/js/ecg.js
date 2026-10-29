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
  let episodioActivo = null;
  let dispositivoEcg = null;
  let isSaving = false;
  let saveConfirmed = false;
  let canSubmitCapture = true;
  let needsVerification = false;
  let savedResultId = null;

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

  function sameCapture(left, right) {
    return Boolean(
      left && right &&
      left.frecuencia_muestreo_hz === right.frecuencia_muestreo_hz &&
      left.unidad === right.unidad &&
      Array.isArray(left.muestras) && Array.isArray(right.muestras) &&
      left.muestras.length === right.muestras.length &&
      left.muestras.every((sample, index) => sample === right.muestras[index])
    );
  }

  function updatePersistenceControls() {
    const hasEpisode = episodioActivo !== null &&
      Number.isSafeInteger(episodioActivo.id) && episodioActivo.id > 0;
    const saveButton = app.querySelector("#guardar-resultado");
    const verifyButton = app.querySelector("#verificar-resultado");
    app.querySelector("#persistencia-panel").hidden = false;
    app.querySelector("#sin-contexto-persistencia").hidden = hasEpisode;
    saveButton.hidden = false;
    saveButton.disabled = !(hasEpisode && dispositivoEcg && capture && canSubmitCapture && !saveConfirmed && !isSaving);
    verifyButton.hidden = !(hasEpisode && capture && needsVerification);
    verifyButton.disabled = isSaving;
  }

  async function loadEpisodeContext() {
    const rawId = new URLSearchParams(window.location.search).get("episodio_id");
    if (rawId === null) {
      app.querySelector("#episodio-contexto").textContent = "No se recibió un episodio activo. La señal puede simularse, pero el guardado queda deshabilitado.";
      app.querySelector("#episodio-persistencia").textContent = "Sin episodio validado. Abrí esta pantalla desde el episodio real para habilitar el guardado.";
      app.querySelector("#dispositivo-persistencia").textContent = "No se buscará dispositivo hasta validar un episodio.";
      app.querySelector("#estado-guardado").textContent = "Guardado no disponible: falta un episodio real.";
      updatePersistenceControls();
      return;
    }
    const episodioId = Number(rawId);
    if (!/^[1-9]\d*$/.test(rawId) || !Number.isSafeInteger(episodioId)) {
      app.querySelector("#episodio-contexto").textContent = "El episodio_id de la URL no es un identificador positivo válido; no se habilitó el guardado.";
      reportError(new Error("episodio_id inválido."));
      app.querySelector("#estado-guardado").textContent = "Guardado no disponible: el episodio_id no es válido.";
      updatePersistenceControls();
      return;
    }

    const contextMessage = app.querySelector("#episodio-contexto");
    const persistenceMessage = app.querySelector("#episodio-persistencia");
    contextMessage.textContent = `Verificando el episodio de prueba ${episodioId}…`;
    app.querySelector("#persistencia-panel").hidden = false;
    app.querySelector("#sin-contexto-persistencia").hidden = true;
    persistenceMessage.textContent = `Episodio de prueba #${episodioId}: verificando circuito en la API.`;
    try {
      const episode = await requestJson(`${API}/episodios/${episodioId}`, {
        headers: { Accept: "application/json" },
      });
      if (episode.id !== episodioId || !["GUARDIA", "COMPLETO"].includes(episode.tipo_circuito)) {
        throw new Error("La API no devolvió un episodio válido de GUARDIA o COMPLETO.");
      }
      episodioActivo = episode;
      if (episode.tipo_circuito === "GUARDIA") {
        contextMessage.textContent = `Episodio #${episode.id}, circuito GUARDIA. Modo de prueba técnica; no se recibió clasificación roja y no se declara completado el flujo rojo HU-09.`;
      } else {
        contextMessage.textContent = `Episodio #${episode.id}, circuito COMPLETO. Prueba técnica HU-14; no requiere clasificación roja.`;
      }
      persistenceMessage.textContent = `Episodio #${episode.id} · ${episode.tipo_circuito} · estado ${episode.estado}.`;

      const devices = await requestJson(`${API}/dispositivos`, {
        headers: { Accept: "application/json" },
      });
      if (!Array.isArray(devices)) throw new Error("La API de dispositivos devolvió un formato inválido.");
      dispositivoEcg = devices.find((device) =>
        device.codigo === "001" &&
        device.tipo === "ECG" &&
        device.activo === true &&
        device.estado === "DISPONIBLE" &&
        Number.isSafeInteger(device.id) && device.id > 0
      ) ?? null;
      if (dispositivoEcg === null) {
        throw new Error("No se encontró el dispositivo ECG de código 001 activo y disponible. No se puede guardar la captura.");
      }
      app.querySelector("#dispositivo-persistencia").textContent =
        `Dispositivo verificado por la API: ${dispositivoEcg.codigo} (ID ${dispositivoEcg.id}).`;
    } catch (error) {
      dispositivoEcg = null;
      const detail = error instanceof Error ? error.message : "No se pudo verificar el episodio o el dispositivo.";
      app.querySelector("#dispositivo-persistencia").textContent = detail;
      app.querySelector("#estado-guardado").textContent = "No se puede guardar la captura: " + detail;
      reportError(error);
    } finally {
      updatePersistenceControls();
    }
  }

  async function obtenerResultadosPersistidos() {
    const response = await requestJson(`${API}/ecg/resultados/${episodioActivo.id}`, {
      headers: { Accept: "application/json" },
    });
    if (
      response.episodio_id !== episodioActivo.id || response.modulo !== "ecg" ||
      !Array.isArray(response.resultados)
    ) {
      throw new Error("La consulta devolvió resultados incompatibles con el episodio ECG.");
    }
    return response.resultados;
  }

  async function verificarResultadoPendiente() {
    if (!episodioActivo || !capture || isSaving) return;
    isSaving = true;
    updatePersistenceControls();
    try {
      const results = await obtenerResultadosPersistidos();
      const match = results.find((result) => sameCapture(result.data, capture));
      needsVerification = false;
      if (match) {
        canSubmitCapture = false;
        app.querySelector("#estado-guardado").textContent =
          `La consulta encontró el resultado #${match.id} con estas mismas muestras. No se reenvió el POST para evitar un posible duplicado; esto no confirma que corresponda a la última solicitud.`;
      } else {
        canSubmitCapture = true;
        app.querySelector("#estado-guardado").textContent =
          "La consulta no encontró un resultado con estas muestras para el episodio. Podés reintentar el guardado.";
      }
    } catch (error) {
      needsVerification = true;
      canSubmitCapture = false;
      app.querySelector("#estado-guardado").textContent =
        `No se pudo verificar el estado en la API. Para evitar duplicados, el reenvío sigue bloqueado: ${error instanceof Error ? error.message : "error de consulta"}`;
    } finally {
      isSaving = false;
      updatePersistenceControls();
    }
  }

  async function reconcileUnconfirmedSave(error) {
    canSubmitCapture = false;
    needsVerification = true;
    app.querySelector("#estado-guardado").textContent =
      `El POST no recibió confirmación: ${error instanceof Error ? error.message : "error de red"} Consultando antes de permitir un reintento…`;
    updatePersistenceControls();
    try {
      const results = await obtenerResultadosPersistidos();
      const match = results.find((result) => sameCapture(result.data, capture));
      needsVerification = false;
      if (match) {
        app.querySelector("#estado-guardado").textContent =
          `La consulta encontró el resultado #${match.id} con estas mismas muestras. No se declara confirmado el POST actual ni se reenvía para evitar duplicarlo.`;
      } else {
        canSubmitCapture = true;
        app.querySelector("#estado-guardado").textContent =
          "El POST no fue confirmado y la consulta no encontró estas muestras. Podés reintentar.";
      }
    } catch (queryError) {
      needsVerification = true;
      app.querySelector("#estado-guardado").textContent =
        `No se confirmó el POST y tampoco se pudo consultar el estado (${queryError instanceof Error ? queryError.message : "error de consulta"}). Verificá antes de reintentar.`;
    }
  }

  async function guardarCaptura() {
    if (!episodioActivo || !Number.isSafeInteger(episodioActivo.id) || episodioActivo.id <= 0 ||
        !dispositivoEcg || !capture || isSaving || saveConfirmed || !canSubmitCapture) return;
    isSaving = true;
    app.querySelector("#estado-guardado").textContent = "Enviando las muestras simuladas a la API…";
    updatePersistenceControls();
    try {
      const saved = await requestJson(`${API}/ecg/resultados`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          episodio_id: episodioActivo.id,
          dispositivo_id: dispositivoEcg.id,
          origen: "SIMULADOR",
          data: capture,
        }),
      });
      if (!Number.isSafeInteger(saved.resultado_id) || saved.resultado_id <= 0) {
        throw new Error("La respuesta del POST no incluyó un resultado_id válido.");
      }
      saveConfirmed = true;
      savedResultId = saved.resultado_id;
      canSubmitCapture = false;
      needsVerification = true;
      app.querySelector("#estado-guardado").textContent =
        `La API confirmó el guardado del resultado #${savedResultId}. Verificando mediante la consulta del episodio…`;
      updatePersistenceControls();
      try {
        const results = await obtenerResultadosPersistidos();
        mostrarResultados(results);
        if (results.some((result) => result.id === savedResultId && sameCapture(result.data, capture))) {
          needsVerification = false;
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó y la consulta verificó el guardado del resultado #${savedResultId}. Origen: SIMULADOR.`;
        } else {
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó el resultado #${savedResultId}, pero todavía no apareció en la consulta. No vuelvas a enviarlo.`;
        }
      } catch (queryError) {
        app.querySelector("#estado-guardado").textContent =
          `La API confirmó el resultado #${savedResultId}, pero falló la consulta de verificación: ${queryError instanceof Error ? queryError.message : "error de consulta"}. No vuelvas a enviarlo.`;
      }
    } catch (error) {
      await reconcileUnconfirmedSave(error);
    } finally {
      isSaving = false;
      updatePersistenceControls();
    }
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
    app.querySelector("#trazo-senal").setAttribute("points", "");
    app.querySelector("#cantidad-final").textContent = "—";
    app.querySelector("#frecuencia-final").textContent = "—";
    app.querySelector("#unidad-final").textContent = "—";
    app.querySelector("#estado-guardado").textContent = "";
    saveConfirmed = false;
    canSubmitCapture = true;
    needsVerification = false;
    savedResultId = null;
    updatePersistenceControls();
  }

  function hasTechnicalInterference(samples) {
    return samples.length > 1 && samples.every((sample) => sample === samples[0]);
  }

  async function presentSamples(data) {
    const shown = [];
    const batchSize = 25;
    for (let offset = 0; offset < data.muestras.length; offset += batchSize) {
      await delay(20);
      if (stopRequested) break;
      for (const sample of data.muestras.slice(offset, offset + batchSize)) {
        shown.push(sample);
      }
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
    app.querySelector("#cantidad-final").textContent = String(capture.muestras.length);
    app.querySelector("#frecuencia-final").textContent = `${capture.frecuencia_muestreo_hz} Hz`;
    app.querySelector("#unidad-final").textContent = capture.unidad;
    const state = app.querySelector("#estado-simulacion");
    state.textContent = stopRequested
      ? "Simulación detenida. La curva parcial queda disponible para revisar o repetir."
      : "Simulación finalizada. La curva está disponible para revisar o guardar.";
    app.querySelector("#detener-simulacion").hidden = true;
    updatePersistenceControls();
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
        updatePersistenceControls();
      }
    } catch (error) {
      app.querySelector("#estado-simulacion").textContent = "No se pudo cargar la señal ECG simulada. Intentá nuevamente.";
      reportError(error);
    } finally {
      isCapturing = false;
      app.querySelector("#iniciar-simulacion").disabled = false;
      app.querySelector("#detener-simulacion").hidden = true;
      showStep(currentStep, true);
      updatePersistenceControls();
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
  app.querySelector("#guardar-resultado").addEventListener("click", guardarCaptura);
  app.querySelector("#verificar-resultado").addEventListener("click", verificarResultadoPendiente);
  showStep(0);
  updatePersistenceControls();
  void loadEpisodeContext();
})();
