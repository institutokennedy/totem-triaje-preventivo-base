(() => {
  "use strict";

  const API = "/api/v1";
  const MUESTRAS_CAPTURA = 2500;
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
    "Adquisición ECG",
    "Resumen de captura",
  ];
  const navItems = [...app.querySelectorAll(".steps li")];
  let currentStep = 0;
  let episodioActivo = null;
  let dispositivoEcg = null;
  let capturaActual = null;
  let sensorCapturesById = new Map();
  let isCapturing = false;
  let pollingGeneration = 0;
  let pollingTimer = null;
  let acquisitionId = null;

  function showStep(index, preserveError = false) {
    currentStep = index;
    app.dataset.step = String(index);
    stepPanels.forEach((panel, panelIndex) => { panel.hidden = panelIndex !== index; });
    navItems.forEach((item, itemIndex) => {
      if (itemIndex === index) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    app.querySelector("#paso-actual").textContent =
      `Paso ${index + 1} de ${stepPanels.length}: ${stepNames[index]}`;
    app.querySelector("#paso-anterior").disabled = index === 0 || isCapturing;
    const next = app.querySelector("#paso-siguiente");
    next.hidden = index === stepPanels.length - 1;
    next.disabled = isCapturing ||
      (index === 1 && !app.querySelector("#aceptar-referencia-electrodos").checked) ||
      (index === 2 && capturaActual === null);
    if (!preserveError) app.querySelector("#error").hidden = true;
  }

  function reportError(error) {
    const message = error instanceof Error
      ? error.message
      : "Ocurrió un error técnico inesperado.";
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

  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = formatApiDetail(body.detail) || `HTTP ${response.status}`;
      throw new Error(`${detail} (${response.status}).`);
    }
    return body;
  }

  function setStatus(message) {
    app.querySelector("#estado-fisico").textContent = message;
  }

  function updateStartButton() {
    const ready = episodioActivo?.estado === "INICIADO" &&
      Number.isSafeInteger(episodioActivo.id) && episodioActivo.id > 0 &&
      dispositivoEcg !== null &&
      app.querySelector("#esp32-url").value.trim().length > 0;
    app.querySelector("#iniciar-ecg").disabled = !ready || isCapturing;
  }

  async function loadEpisodeContext() {
    const rawId = new URLSearchParams(window.location.search).get("episodio_id");
    if (rawId === null) {
      app.querySelector("#episodio-contexto").textContent =
        "No se recibió un episodio activo. Abrí esta pantalla desde un episodio real para iniciar la adquisición.";
      app.querySelector("#episodio-persistencia").textContent =
        "Sin episodio validado. La adquisición y el guardado requieren un episodio real.";
      app.querySelector("#dispositivo-persistencia").textContent =
        "No se buscará el dispositivo hasta validar un episodio.";
      setStatus("Error: falta un episodio válido.");
      updateStartButton();
      return;
    }
    const episodioId = Number(rawId);
    if (!/^[1-9]\d*$/.test(rawId) || !Number.isSafeInteger(episodioId)) {
      app.querySelector("#episodio-contexto").textContent =
        "El episodio_id de la URL no es un identificador positivo válido.";
      setStatus("Error: el episodio no es válido.");
      reportError(new Error("episodio_id inválido."));
      updateStartButton();
      return;
    }

    app.querySelector("#episodio-contexto").textContent =
      `Verificando el episodio #${episodioId}…`;
    app.querySelector("#episodio-persistencia").textContent =
      `Episodio #${episodioId}: verificando estado en la API.`;
    try {
      const episode = await requestJson(`${API}/episodios/${episodioId}`, {
        headers: { Accept: "application/json" },
      });
      if (
        episode.id !== episodioId ||
        !["GUARDIA", "COMPLETO"].includes(episode.tipo_circuito)
      ) {
        throw new Error("La API no devolvió un episodio válido de GUARDIA o COMPLETO.");
      }
      episodioActivo = episode;
      app.querySelector("#episodio-contexto").textContent =
        `Episodio #${episode.id} · ${episode.tipo_circuito} · estado ${episode.estado}.`;
      app.querySelector("#episodio-inicio").textContent =
        `Inicio: ${formatEpisodeDate(episode.iniciado_en)}`;
      app.querySelector("#episodio-persistencia").textContent =
        `Episodio #${episode.id} · ${episode.tipo_circuito} · estado ${episode.estado}.`;

      const devices = await requestJson(`${API}/dispositivos`, {
        headers: { Accept: "application/json" },
      });
      if (!Array.isArray(devices)) {
        throw new Error("La API de dispositivos devolvió un formato inválido.");
      }
      dispositivoEcg = devices.find((device) =>
        device.codigo === "ECG-001" &&
        device.tipo === "ECG" &&
        device.activo === true &&
        device.estado === "DISPONIBLE" &&
        Number.isSafeInteger(device.id) && device.id > 0
      ) ?? null;
      if (dispositivoEcg === null) {
        throw new Error(
          "No se encontró el dispositivo ECG-001 activo y disponible."
        );
      }
      app.querySelector("#dispositivo-persistencia").textContent =
        `Dispositivo verificado por la API: ${dispositivoEcg.codigo} (ID ${dispositivoEcg.id}).`;
      try {
        await cargarHistorial();
      } catch (error) {
        app.querySelector("#estado-guardado").textContent =
          `No se pudo cargar el historial ECG: ${error.message}`;
        reportError(error);
      }
      if (episode.estado !== "INICIADO") {
        setStatus("Error: el episodio debe estar INICIADO para adquirir ECG.");
      } else {
        setStatus("Listo para iniciar.");
      }
    } catch (error) {
      dispositivoEcg = null;
      const detail = error instanceof Error
        ? error.message
        : "No se pudo verificar el episodio o el dispositivo.";
      app.querySelector("#dispositivo-persistencia").textContent = detail;
      setStatus(`Error de comunicación o contexto: ${detail}`);
      reportError(error);
    } finally {
      updateStartButton();
    }
  }

  function deviceBaseUrl() {
    const raw = app.querySelector("#esp32-url").value.trim();
    if (!raw) throw new Error("Ingresá la dirección del ESP32.");
    const value = /^[a-z][a-z\d+.-]*:\/\//i.test(raw) ? raw : `http://${raw}`;
    const url = new URL(value);
    if (
      url.protocol !== "http:" || url.username || url.password ||
      (url.pathname !== "/" && url.pathname !== "") || url.search || url.hash
    ) {
      throw new Error("Ingresá solo la dirección HTTP local del ESP32, sin rutas.");
    }
    return url.origin;
  }

  async function requestDeviceJson(baseUrl, path, options = {}) {
    return requestJson(`${baseUrl}${path}`, {
      ...options,
      mode: "cors",
      cache: "no-store",
    });
  }

  async function readDeviceState(baseUrl) {
    const state = await requestDeviceJson(baseUrl, "/api/ecg", {
      headers: { Accept: "application/json" },
    });
    if (
      !Array.isArray(state.muestras) ||
      !Number.isInteger(state.cantidad_muestras) ||
      state.cantidad_muestras < 0 ||
      state.cantidad_muestras > MUESTRAS_CAPTURA ||
      state.muestras.length !== state.cantidad_muestras ||
      !state.muestras.every((sample) =>
        Number.isInteger(sample) && sample >= 0 && sample <= 4095
      ) ||
      state.frecuencia_muestreo_hz !== 250 ||
      state.unidad !== "ADC"
    ) {
      throw new Error("El ESP32 devolvió un estado ECG incompatible.");
    }
    return state;
  }

  async function obtenerResultadosPersistidos() {
    const response = await requestJson(
      `${API}/ecg/resultados/${episodioActivo.id}`,
      { headers: { Accept: "application/json" } }
    );
    if (
      response.episodio_id !== episodioActivo.id ||
      response.modulo !== "ecg" ||
      !Array.isArray(response.resultados)
    ) {
      throw new Error("La consulta devolvió resultados incompatibles con el episodio ECG.");
    }
    return response.resultados;
  }

  function capturaSensorValida(result) {
    const data = result?.data;
    return Number.isSafeInteger(result?.id) && result.id > 0 &&
      data?.frecuencia_muestreo_hz === 250 &&
      data?.unidad === "ADC" &&
      typeof data.adquisicion_id === "string" &&
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(data.adquisicion_id) &&
      Array.isArray(data.muestras) && data.muestras.length === MUESTRAS_CAPTURA &&
      data.muestras.every((sample) =>
        Number.isInteger(sample) && sample >= 0 && sample <= 4095
      );
  }

  function actualizarListaCapturasFisicas() {
    const selector = app.querySelector("#capturas-historicas");
    const capturas = [...sensorCapturesById.values()]
      .sort((left, right) => right.id - left.id);
    const options = capturas.map((result) => {
      const option = document.createElement("option");
      option.value = String(result.id);
      option.textContent =
        `Resultado #${result.id} · ${result.data.muestras.length} muestras · ${result.data.frecuencia_muestreo_hz} Hz`;
      return option;
    });
    selector.replaceChildren(...options);
    selector.hidden = capturas.length === 0;
  }

  function drawSignal(samples, frequency, unit) {
    const trace = app.querySelector("#trazo-senal");
    if (samples.length === 0) {
      trace.setAttribute("points", "");
      return;
    }

    const minimum = Math.min(...samples);
    const maximum = Math.max(...samples);
    const range = maximum - minimum || 1;
    const points = samples.map((sample, index) => {
      const x = 72 + index * (548 / Math.max(samples.length - 1, 1));
      const y = 160 - ((sample - minimum) / range) * 140;
      return `${x},${y}`;
    });
    trace.setAttribute("points", points.join(" "));
    app.querySelector("#amplitud-maxima").textContent = String(maximum);
    app.querySelector("#amplitud-centro-escala").textContent =
      String((minimum + maximum) / 2);
    app.querySelector("#amplitud-minima").textContent = String(minimum);
    const duration = (samples.length - 1) / frequency;
    app.querySelector("#tiempo-medio").textContent = `${(duration / 2).toFixed(3)} s`;
    app.querySelector("#tiempo-total").textContent = `${duration.toFixed(3)} s`;
    app.querySelector("#unidad-eje").textContent = `Amplitud (${unit})`;
  }

  function clearSignal() {
    drawSignal([], 250, "ADC");
    app.querySelector("#amplitud-maxima").textContent = "—";
    app.querySelector("#amplitud-centro-escala").textContent = "—";
    app.querySelector("#amplitud-minima").textContent = "—";
    app.querySelector("#tiempo-medio").textContent = "— s";
    app.querySelector("#tiempo-total").textContent = "— s";
    app.querySelector("#unidad-eje").textContent = "Amplitud —";
    app.querySelector("#cantidad-final").textContent = "—";
    app.querySelector("#frecuencia-final").textContent = "—";
    app.querySelector("#unidad-final").textContent = "—";
  }

  function actualizarCapturaGuardada(result, isNewCapture = false) {
    if (!capturaSensorValida(result)) {
      throw new Error("La API devolvió una captura física que no cumple el contrato ECG.");
    }
    const data = result.data;
    capturaActual = {
      adquisicion_id: data.adquisicion_id,
      frecuencia_muestreo_hz: data.frecuencia_muestreo_hz,
      muestras: [...data.muestras],
      unidad: data.unidad,
    };
    drawSignal(capturaActual.muestras, capturaActual.frecuencia_muestreo_hz, capturaActual.unidad);
    app.querySelector("#cantidad-final").textContent = String(capturaActual.muestras.length);
    app.querySelector("#frecuencia-final").textContent =
      `${capturaActual.frecuencia_muestreo_hz} Hz`;
    app.querySelector("#unidad-final").textContent = capturaActual.unidad;
    app.querySelector("#origen-resumen").textContent =
      `Origen: SENSOR · ESP32 ${dispositivoEcg?.codigo ?? "ECG-001"} · resultado #${result.id}.`;
    app.querySelector("#descripcion-resumen").textContent =
      "Captura ADC original recibida y guardada por la API. Sin filtros ni identificación automática de ondas.";
    app.querySelector("#capturas-historicas").value = String(result.id);
    app.querySelector("#estado-guardado").textContent =
      `Resultado guardado: la API confirmó la captura #${result.id}.`;
    setStatus(isNewCapture
      ? `Resultado guardado por la API · captura #${result.id}.`
      : `Captura histórica #${result.id}.`);
    updateStartButton();
    showStep(currentStep, true);
  }

  async function cargarHistorial() {
    const results = await obtenerResultadosPersistidos();
    for (const result of results) {
      if (result?.data?.unidad === "ADC" && capturaSensorValida(result)) {
        sensorCapturesById.set(result.id, result);
      }
    }
    actualizarListaCapturasFisicas();
    return results;
  }

  function updateLiveSignal(state) {
    const samples = state.muestras;
    if (samples.length > 0) {
      drawSignal(samples, state.frecuencia_muestreo_hz, state.unidad || "ADC");
      app.querySelector("#cantidad-final").textContent = String(samples.length);
      app.querySelector("#frecuencia-final").textContent =
        `${state.frecuencia_muestreo_hz} Hz`;
      app.querySelector("#unidad-final").textContent = state.unidad || "ADC";
    } else if (state.captura_abortada || state.adquisicion_id === "") {
      clearSignal();
    }
  }

  function stopPolling() {
    pollingGeneration += 1;
    if (pollingTimer !== null) {
      window.clearTimeout(pollingTimer);
      pollingTimer = null;
    }
    isCapturing = false;
    updateStartButton();
  }

  function finishWithError(message, error = null) {
    stopPolling();
    setStatus(`Error de comunicación o adquisición: ${message}`);
    app.querySelector("#estado-guardado").textContent =
      "No se confirmó un resultado guardado.";
    if (error) reportError(error);
    updateStartButton();
  }

  async function pollAcquisition(baseUrl, generation) {
    if (generation !== pollingGeneration || !isCapturing) return;
    try {
      const state = await readDeviceState(baseUrl);
      if (generation !== pollingGeneration) return;
      if (state.episodio_id !== episodioActivo.id) {
        throw new Error("El ESP32 está configurado con otro episodio.");
      }
      if (state.adquisicion_id) acquisitionId = state.adquisicion_id;
      updateLiveSignal(state);

      if (!state.electrodos_conectados && state.adquisicion_en_curso) {
        finishWithError("el ESP32 detectó electrodos desconectados y abortó la captura.");
        return;
      }
      if (state.captura_pendiente) {
        if (state.codigo_http < 200 || state.codigo_http >= 300) {
          setStatus(`Error de guardado (${state.codigo_http || "red"}): ${state.mensaje} Se conserva la captura y el ESP32 reintentará con el mismo UUID.`);
          reportError(new Error(state.mensaje || "La API no confirmó el guardado."));
        } else {
          setStatus("Procesando y guardando la captura completa en la API…");
        }
      } else if (state.adquisicion_en_curso) {
        setStatus(`Adquiriendo ECG: ${state.cantidad_muestras}/${MUESTRAS_CAPTURA} muestras reales.`);
      }

      if (acquisitionId) {
        try {
          const results = await obtenerResultadosPersistidos();
          const saved = results.find((result) =>
            result?.data?.adquisicion_id === acquisitionId
          );
          if (saved) {
            sensorCapturesById.set(saved.id, saved);
            actualizarListaCapturasFisicas();
            stopPolling();
            app.querySelector("#error").hidden = true;
            actualizarCapturaGuardada(saved, true);
            return;
          }
        } catch (error) {
          setStatus(`Error consultando el guardado en la API: ${error.message}`);
          reportError(error);
        }
      }

      if (
        !state.captura_pendiente && !state.adquisicion_en_curso &&
        typeof state.mensaje === "string" && /abortad[ao]/i.test(state.mensaje)
      ) {
        finishWithError(state.mensaje);
        return;
      }
      if (
        !state.captura_pendiente && !state.adquisicion_en_curso &&
        state.cantidad_muestras === 0 &&
        /guardad[ao]/i.test(state.mensaje || "")
      ) {
        setStatus("La API confirmó el envío; verificando el resultado del episodio…");
      } else if (!state.electrodos_conectados && !state.captura_pendiente) {
        setStatus("Esperando señal: conectá los electrodos al AD8232.");
      }
    } catch (error) {
      setStatus(`Error de comunicación con ESP32: ${error.message}. Reintentando consulta…`);
      reportError(error);
    }
    if (generation === pollingGeneration && isCapturing) {
      pollingTimer = window.setTimeout(
        () => { void pollAcquisition(baseUrl, generation); },
        1000
      );
    }
  }

  async function esperarElectrodos(baseUrl) {
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      const state = await readDeviceState(baseUrl);
      if (!state.wifi_conectado) {
        throw new Error("El ESP32 no está conectado a la red Wi-Fi.");
      }
      if (state.captura_pendiente || state.adquisicion_en_curso) return state;
      if (state.electrodos_conectados) return state;
      setStatus("Esperando señal: conectá los electrodos al AD8232.");
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
    throw new Error("No se detectó señal de electrodos en 30 segundos.");
  }

  async function iniciarECG() {
    if (
      isCapturing || episodioActivo?.estado !== "INICIADO" ||
      !dispositivoEcg || !Number.isSafeInteger(episodioActivo.id)
    ) return;

    let baseUrl;
    try {
      baseUrl = deviceBaseUrl();
    } catch (error) {
      setStatus(`Listo para iniciar: ${error.message}`);
      reportError(error);
      return;
    }

    capturaActual = null;
    acquisitionId = null;
    sensorCapturesById = new Map();
    clearSignal();
    isCapturing = true;
    updateStartButton();
    showStep(currentStep, true);
    app.querySelector("#estado-guardado").textContent = "";
    setStatus("Conectando con ESP32 y verificando el episodio…");
    app.querySelector("#estado-dispositivo").textContent =
      "Conexión en curso con ESP32.";
    const generation = ++pollingGeneration;

    try {
      await cargarHistorial();
      let state = await esperarElectrodos(baseUrl);
      if (state.adquisicion_en_curso || state.captura_pendiente) {
        if (state.episodio_id !== episodioActivo.id || !state.adquisicion_id) {
          throw new Error("El ESP32 tiene otra adquisición activa o pendiente.");
        }
        acquisitionId = state.adquisicion_id;
        setStatus("Adquisición existente detectada; esperando su guardado sin iniciar otra.");
      } else {
        const formData = new URLSearchParams({
          episodio_id: String(episodioActivo.id),
          dispositivo_id: String(dispositivoEcg.id),
        });
        const configured = await requestDeviceJson(baseUrl, "/configurar", {
          method: "POST",
          body: formData,
        });
        if (
          configured.episodio_id !== episodioActivo.id ||
          configured.dispositivo_id !== dispositivoEcg.id
        ) {
          throw new Error("El ESP32 no confirmó el episodio y dispositivo solicitados.");
        }
        await requestDeviceJson(baseUrl, "/iniciar", { method: "POST" });
        setStatus("Adquiriendo ECG: esperando las primeras muestras del AD8232…");
      }
      app.querySelector("#error").hidden = true;
      app.querySelector("#estado-dispositivo").textContent =
        "ESP32 conectado; adquisición física en curso.";
      await pollAcquisition(baseUrl, generation);
    } catch (error) {
      isCapturing = false;
      updateStartButton();
      setStatus(`Error de comunicación o inicio: ${error.message}`);
      reportError(error);
      app.querySelector("#estado-dispositivo").textContent =
        "No se pudo confirmar la conexión o el inicio del ESP32.";
    }
  }

  app.querySelector("#paso-anterior").addEventListener("click", () => {
    if (currentStep > 0 && !isCapturing) showStep(currentStep - 1);
  });
  app.querySelector("#paso-siguiente").addEventListener("click", () => {
    if (currentStep < stepPanels.length - 1 && !(currentStep === 2 && !capturaActual)) {
      showStep(currentStep + 1);
    }
  });
  app.querySelector("#aceptar-referencia-electrodos").addEventListener("change", (event) => {
    app.querySelector("#paso-siguiente").disabled = !event.target.checked;
    if (currentStep === 1) showStep(1);
  });
  app.querySelector("#iniciar-ecg").addEventListener("click", () => {
    void iniciarECG();
  });
  app.querySelector("#esp32-url").addEventListener("input", updateStartButton);
  app.querySelector("#capturas-historicas").addEventListener("change", (event) => {
    const result = sensorCapturesById.get(Number(event.target.value));
    if (result) actualizarCapturaGuardada(result);
  });

  showStep(0);
  updateStartButton();
  void loadEpisodeContext();
})();
