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

  function formatApiDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const location = Array.isArray(item.loc) ? item.loc.join(" → ") : "";
        return [location, item.msg].filter(Boolean).join(": ");
      }).filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
    return detail === undefined ? "" : JSON.stringify(detail);
  }

  function formatEpisodeDate(value) {
    if (typeof value !== "string") return "No informada por la API.";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "No informada por la API.";
    return new Intl.DateTimeFormat("es-AR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = formatApiDetail(body.detail) || `HTTP ${response.status}`;
      throw new Error(`${detail} (${response.status}).`);
    }
    return body;
  }

  function sameAcquisition(left, right) {
    return Boolean(
      left && right &&
      typeof left.adquisicion_id === "string" &&
      left.adquisicion_id === right.adquisicion_id
    );
  }

  function updatePersistenceControls() {
    const hasEpisode = episodioActivo !== null &&
      Number.isSafeInteger(episodioActivo.id) && episodioActivo.id > 0;
    const saveButton = app.querySelector("#guardar-resultado");
    const verifyButton = app.querySelector("#verificar-resultado");
    const captureChangesBlocked = isCapturing || isSaving || needsVerification;
    app.querySelector("#persistencia-panel").hidden = false;
    app.querySelector("#sin-contexto-persistencia").hidden = hasEpisode;
    saveButton.hidden = false;
    saveButton.disabled = !(hasEpisode && dispositivoEcg && capture && canSubmitCapture && !saveConfirmed && !isSaving);
    verifyButton.hidden = !(hasEpisode && capture && needsVerification);
    verifyButton.disabled = isSaving;
    app.querySelector("#iniciar-simulacion").disabled = captureChangesBlocked;
    app.querySelector("#repetir-simulacion").disabled = captureChangesBlocked;
    app.querySelector("#repetir-ecg").disabled = captureChangesBlocked;
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
      app.querySelector("#episodio-inicio").textContent =
        `Inicio: ${formatEpisodeDate(episode.iniciado_en)}`;

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
      const match = results.find((result) => sameAcquisition(result.data, capture));
      if (saveConfirmed) {
        const confirmedResult = results.find((result) =>
          result.id === savedResultId && sameAcquisition(result.data, capture)
        );
        if (confirmedResult) {
          needsVerification = false;
          app.querySelector("#error").hidden = true;
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó y la consulta verificó el guardado del resultado #${savedResultId}. Origen: SIMULADOR.`;
        } else {
          needsVerification = true;
          canSubmitCapture = false;
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó el resultado #${savedResultId}, pero todavía no apareció en la consulta. No vuelvas a enviarlo.`;
        }
      } else if (match) {
        needsVerification = false;
        canSubmitCapture = false;
        app.querySelector("#estado-guardado").textContent =
          `La consulta encontró la adquisición #${match.id}. No se reenvió el POST para evitar un duplicado.`;
      } else {
        needsVerification = false;
        canSubmitCapture = true;
        app.querySelector("#estado-guardado").textContent =
          "La consulta no encontró un resultado con estas muestras para el episodio. Podés reintentar el guardado.";
      }
    } catch (error) {
      needsVerification = true;
      canSubmitCapture = false;
      app.querySelector("#estado-guardado").textContent =
        `No se pudo verificar el estado en la API. Para evitar duplicados, el reenvío sigue bloqueado: ${error instanceof Error ? error.message : "error de consulta"}`;
      reportError(error);
    } finally {
      isSaving = false;
      updatePersistenceControls();
    }
  }

  async function reconcileUnconfirmedSave(error) {
    const postError = error instanceof Error ? error.message : "error de API o red";
    canSubmitCapture = false;
    needsVerification = true;
    app.querySelector("#estado-guardado").textContent =
      `El POST falló o no recibió confirmación: ${postError} Consultando antes de permitir un reintento…`;
    reportError(error);
    updatePersistenceControls();
    try {
      const results = await obtenerResultadosPersistidos();
      const match = results.find((result) => sameAcquisition(result.data, capture));
      needsVerification = false;
      if (match) {
        canSubmitCapture = false;
        app.querySelector("#estado-guardado").textContent =
          `El POST falló o no recibió confirmación: ${postError} La consulta encontró la adquisición como resultado #${match.id}; no se reenvió para evitar un duplicado.`;
      } else {
        canSubmitCapture = true;
        app.querySelector("#estado-guardado").textContent =
          `El POST falló: ${postError} La consulta no encontró estas muestras para el episodio; podés reintentar.`;
      }
    } catch (queryError) {
      needsVerification = true;
      canSubmitCapture = false;
      app.querySelector("#estado-guardado").textContent =
        `El POST falló o no recibió confirmación: ${postError} Además, no se pudo consultar el estado (${queryError instanceof Error ? queryError.message : "error de consulta"}). Verificá antes de reintentar.`;
      reportError(queryError);
    }
  }

  async function guardarCaptura() {
    if (!episodioActivo || !Number.isSafeInteger(episodioActivo.id) || episodioActivo.id <= 0 ||
        !dispositivoEcg || !capture || isSaving || needsVerification || saveConfirmed || !canSubmitCapture) return;
    isSaving = true;
    app.querySelector("#estado-guardado").textContent = "Comprobando que esta adquisición no esté guardada antes de confirmarla…";
    updatePersistenceControls();
    try {
      let existing;
      try {
        existing = await obtenerResultadosPersistidos();
      } catch (error) {
        app.querySelector("#estado-guardado").textContent =
          `No se envió el POST porque no se pudo comprobar si la captura ya existe: ${error instanceof Error ? error.message : "error de consulta"}`;
        reportError(error);
        return;
      }

      const duplicate = existing.find((result) => sameAcquisition(result.data, capture));
      if (duplicate) {
        canSubmitCapture = false;
        app.querySelector("#error").hidden = true;
        app.querySelector("#estado-guardado").textContent =
          `Esta adquisición ya existe como resultado #${duplicate.id}. No se creó un duplicado.`;
        return;
      }

      let saved;
      try {
        saved = await requestJson(`${API}/ecg/resultados`, {
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
      } catch (error) {
        await reconcileUnconfirmedSave(error);
        return;
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
        if (results.some((result) => result.id === savedResultId && sameAcquisition(result.data, capture))) {
          needsVerification = false;
          app.querySelector("#error").hidden = true;
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó y la consulta verificó el guardado del resultado #${savedResultId}. Origen: SIMULADOR.`;
        } else {
          app.querySelector("#estado-guardado").textContent =
            `La API confirmó el resultado #${savedResultId}, pero todavía no apareció en la consulta. No vuelvas a enviarlo.`;
        }
      } catch (queryError) {
        reportError(queryError);
        app.querySelector("#estado-guardado").textContent =
          `La API confirmó el resultado #${savedResultId}, pero falló la consulta de verificación: ${queryError instanceof Error ? queryError.message : "error de consulta"}. No vuelvas a enviarlo.`;
      }
    } catch (error) {
      reportError(error);
      app.querySelector("#estado-guardado").textContent =
        `No se pudo completar la confirmación: ${error instanceof Error ? error.message : "error inesperado"}`;
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
      adquisicion_id: data.adquisicion_id,
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
    if (isCapturing || isSaving || needsVerification || flowFinalized) return;
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
        typeof data.adquisicion_id !== "string" ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(data.adquisicion_id) ||
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
    if (isSaving || needsVerification) return;
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
