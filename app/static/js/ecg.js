(() => {
  "use strict";

  const API = "/api/v1";
  const MUESTRAS_CAPTURA = 2500;
  const VENTANA_VISUAL_SEGUNDOS = 10;
  const MUESTRAS_VENTANA_VISUAL = 250 * VENTANA_VISUAL_SEGUNDOS;
  const GRAFICA_X_INICIO = 72;
  const GRAFICA_X_FIN = 620;
  const GRAFICA_Y_INICIO = 20;
  const GRAFICA_Y_FIN = 160;
  const GRAFICA_PASO_X =
    (GRAFICA_X_FIN - GRAFICA_X_INICIO) / MUESTRAS_VENTANA_VISUAL;
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
  let esp32BaseUrl = null;
  let estadoConexion = "DESCONECTADO";
  let conexionTimer = null;
  let pollingGeneration = 0;
  let pollingTimer = null;
  let acquisitionId = null;
  let liveSignalBuffer = createLiveSignalBuffer(MUESTRAS_VENTANA_VISUAL);
  let liveSignalFrame = null;

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
      estadoConexion === "CONECTADO" &&
      esp32BaseUrl !== null;
    app.querySelector("#iniciar-ecg").disabled = !ready || isCapturing;
  }

  function setDeviceConnection(status, detail = "") {
    estadoConexion = status;
    app.querySelector("#estado-dispositivo").textContent =
      `Conexión: ${status}${detail ? ` · ${detail}` : "."}`;
    updateStartButton();
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

  async function requestDeviceJson(baseUrl, path, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4000);
    try {
      return await requestJson(`${baseUrl}${path}`, {
        ...options,
        mode: "cors",
        cache: "no-store",
        signal: controller.signal,
      });
    } finally {
      window.clearTimeout(timeout);
    }
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
      !calibracionADCValida(
        state,
        state.cantidad_muestras,
        true
      ) ||
      state.frecuencia_muestreo_hz !== 250 ||
      state.unidad !== "ADC" ||
      typeof state.wifi_conectado !== "boolean" ||
      typeof state.backend_conectado !== "boolean"
    ) {
      throw new Error("El ESP32 devolvió un estado ECG incompatible.");
    }
    return state;
  }

  async function pollDeviceConnection() {
    if (isCapturing) {
      conexionTimer = window.setTimeout(() => { void pollDeviceConnection(); }, 3000);
      return;
    }

    setDeviceConnection("CONECTANDO", "buscando el ESP32 en la red local");
    try {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 5000);
      let discovery;
      try {
        discovery = await requestJson(`${API}/ecg/conexion`, {
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });
      } finally {
        window.clearTimeout(timeout);
      }
      if (!Array.isArray(discovery.dispositivos)) {
        throw new Error("La API devolvió un resultado de descubrimiento inválido.");
      }
      if (discovery.dispositivos.length === 0) {
        esp32BaseUrl = null;
        setDeviceConnection("DESCONECTADO", "no se detectó un ESP32 ECG por mDNS");
        return;
      }

      let errorConexion = null;
      for (const device of discovery.dispositivos) {
        if (device.codigo !== "ECG-001" || typeof device.base_url !== "string") {
          continue;
        }
        try {
          const url = new URL(device.base_url);
          if (
            url.protocol !== "http:" || url.username || url.password ||
            (url.pathname !== "/" && url.pathname !== "") || url.search || url.hash
          ) {
            throw new Error("El descubrimiento devolvió una URL de ESP32 inválida.");
          }
          const state = await readDeviceState(url.origin);
          if (!state.wifi_conectado) {
            throw new Error("El ESP32 respondió, pero no está conectado al Wi-Fi.");
          }
          if (!state.backend_conectado) {
            throw new Error("El ESP32 respondió, pero todavía no encontró FastAPI por mDNS.");
          }
          esp32BaseUrl = url.origin;
          setDeviceConnection("CONECTADO", "ESP32 y FastAPI responden");
          return;
        } catch (error) {
          errorConexion = error;
        }
      }
      esp32BaseUrl = null;
      const detail = errorConexion instanceof Error
        ? errorConexion.message
        : "el ESP32 anunciado no coincide con ECG-001";
      setDeviceConnection("ERROR", `${detail} (red, CORS o timeout)`);
    } catch (error) {
      esp32BaseUrl = null;
      const detail = error instanceof Error ? error.message : "error de comunicación";
      setDeviceConnection("ERROR", `no se pudo consultar FastAPI: ${detail}`);
    } finally {
      conexionTimer = window.setTimeout(() => { void pollDeviceConnection(); }, 3000);
    }
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
      ) &&
      calibracionADCValida(data, data.muestras.length, false);
  }

  function calibracionADCValida(data, cantidad, permitirListaVacia) {
    const calibration = data?.calibracion_adc;
    const tieneMuestrasMv = Array.isArray(data?.muestras_mV_OUT);
    if (calibration === undefined) {
      return (
        !Object.prototype.hasOwnProperty.call(data ?? {}, "muestras_mV_OUT") &&
        (data?.estado_mV_OUT === undefined ||
          data.estado_mV_OUT === "NO_EVALUABLE")
      );
    }
    if (
      typeof calibration !== "object" ||
      calibration.metodo !== "ESP_IDF_LINE_FITTING" ||
      calibration.adc_unit !== "ADC1" ||
      calibration.gpio !== 34 ||
      calibration.canal !== 6 ||
      calibration.resolucion_bits !== 12 ||
      calibration.atenuacion !== "ADC_11db/ADC_ATTEN_DB_12" ||
      typeof calibration.chip_model !== "string" ||
      calibration.chip_model.length === 0 ||
      !Number.isInteger(calibration.chip_revision) ||
      typeof calibration.esp_idf_version !== "string" ||
      calibration.esp_idf_version.length === 0
    ) {
      return false;
    }
    if (calibration.estado === "ERROR") {
      return (
        Number.isInteger(calibration.error_codigo) &&
        calibration.error_codigo !== 0 &&
        typeof calibration.error === "string" &&
        calibration.error.trim().length > 0 &&
        !tieneMuestrasMv &&
        data.estado_mV_OUT === "NO_EVALUABLE"
      );
    }
    if (calibration.estado === "NO_CONFIABLE") {
      if (!tieneMuestrasMv) {
        return (
          data.estado_mV_OUT === "NO_EVALUABLE" &&
          (calibration.error_codigo === null ||
            calibration.error_codigo === undefined) &&
          typeof calibration.error === "string" &&
          calibration.error.trim().length > 0
        );
      }
      return (
        data.estado_mV_OUT === "NO_CONFIABLE" &&
        typeof calibration.error === "string" &&
        calibration.error.trim().length > 0 &&
        (calibration.error_codigo === null ||
          calibration.error_codigo === undefined) &&
        tieneMuestrasMv &&
        data.muestras_mV_OUT.length === cantidad &&
        data.muestras_mV_OUT.every((sample) =>
          Number.isInteger(sample) && sample >= 0
        )
      );
    }
    const metadatosCalibracionCoherentes =
      calibration.estado === "CALIBRADA" &&
      calibration.fuente === "EFUSE_VREF" &&
      calibration.vref_efuse_raw === 17 &&
      calibration.vref_efuse_mv === 1093 &&
      calibration.chip_model === "ESP32-D0WD-V3" &&
      calibration.chip_revision === 301 &&
      calibration.esp_idf_version === "v5.5.5" &&
      (calibration.error_codigo === null || calibration.error_codigo === undefined) &&
      (calibration.error === null || calibration.error === "");
    if (!metadatosCalibracionCoherentes) return false;
    if (!tieneMuestrasMv) return data.estado_mV_OUT === "NO_EVALUABLE";
    return (
      data.estado_mV_OUT === "NO_CONFIABLE" &&
      data.muestras_mV_OUT.length === cantidad &&
      (permitirListaVacia || cantidad > 0) &&
      data.muestras_mV_OUT.every((sample) =>
        Number.isInteger(sample) && sample >= 0
      )
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

  function createLiveSignalBuffer(capacity) {
    return {
      samples: new Array(capacity),
      discontinuities: new Array(capacity),
      sequences: new Array(capacity),
      head: 0,
      size: 0,
      capacity,
      acquisitionId: null,
      lastCount: 0,
      discontinuityPending: false,
      discontinuitiesCount: 0,
      lastSampleReceivedAt: 0,
      lastSequence: -1,
      frequency: 250,
      unit: "ADC",
    };
  }

  function resetLiveSignalBuffer(buffer, acquisitionId) {
    buffer.head = 0;
    buffer.size = 0;
    buffer.acquisitionId = acquisitionId;
    buffer.lastCount = 0;
    buffer.discontinuityPending = false;
    buffer.discontinuitiesCount = 0;
    buffer.lastSampleReceivedAt = 0;
    buffer.lastSequence = -1;
  }

  function appendLiveSignalState(buffer, state, receivedAt) {
    let changed = false;
    if (
      buffer.acquisitionId !== state.adquisicion_id ||
      state.cantidad_muestras < buffer.lastCount ||
      buffer.unit !== state.unidad
    ) {
      resetLiveSignalBuffer(buffer, state.adquisicion_id);
      changed = true;
    }

    buffer.frequency = state.frecuencia_muestreo_hz;
    buffer.unit = state.unidad;
    const firstNewSample = buffer.lastCount;
    if (firstNewSample < state.cantidad_muestras && buffer.discontinuityPending) {
      buffer.discontinuitiesCount += 1;
    }
    for (let index = firstNewSample; index < state.cantidad_muestras; index += 1) {
      const position = (buffer.head + buffer.size) % buffer.capacity;
      const overwriting = buffer.size === buffer.capacity;
      const target = overwriting ? buffer.head : position;
      buffer.samples[target] = state.muestras[index];
      buffer.discontinuities[target] =
        index === firstNewSample && buffer.discontinuityPending;
      buffer.sequences[target] = index;
      if (overwriting) buffer.head = (buffer.head + 1) % buffer.capacity;
      else buffer.size += 1;
    }

    if (state.cantidad_muestras > firstNewSample) {
      buffer.lastSequence = state.cantidad_muestras - 1;
      buffer.lastSampleReceivedAt = receivedAt;
      buffer.discontinuityPending = false;
      changed = true;
    }
    buffer.lastCount = state.cantidad_muestras;
    return changed;
  }

  function markLiveSignalDiscontinuity(buffer) {
    buffer.discontinuityPending = true;
  }

  function visualAmplitudeScale(samples) {
    if (samples.length === 0) return { baseline: 0, amplitude: 1 };
    let minimum = samples[0];
    let maximum = samples[0];
    for (const sample of samples) {
      minimum = Math.min(minimum, sample);
      maximum = Math.max(maximum, sample);
    }
    const baseline = (minimum + maximum) / 2;
    return {
      baseline,
      amplitude: Math.max(Math.abs(maximum - baseline), 1),
    };
  }

  function liveSignalSamples(buffer) {
    return Array.from({ length: buffer.size }, (_, offset) =>
      buffer.samples[(buffer.head + offset) % buffer.capacity]
    );
  }

  function updateSignalScaleStatus(samples, baseline, unit = "ADC") {
    let lowerRail = 0;
    let upperRail = 0;
    let minimum = samples.length > 0 ? samples[0] : 0;
    let maximum = minimum;
    for (const sample of samples) {
      minimum = Math.min(minimum, sample);
      maximum = Math.max(maximum, sample);
      if (unit === "ADC" && sample === 0) lowerRail += 1;
      if (unit === "ADC" && sample === 4095) upperRail += 1;
    }
    const amplitude = samples.length > 0
      ? Math.max(Math.abs(maximum - baseline), Math.abs(minimum - baseline))
      : 0;
    app.querySelector("#amplitud-maxima").textContent =
      samples.length > 0 ? (baseline + amplitude).toFixed(0) : "—";
    app.querySelector("#amplitud-centro-escala").textContent =
      samples.length > 0 ? baseline.toFixed(1) : "—";
    app.querySelector("#amplitud-minima").textContent =
      samples.length > 0 ? (baseline - amplitude).toFixed(0) : "—";
    if (unit === "mV_OUT") {
      app.querySelector("#unidad-eje").textContent =
        "mV_OUT (tensión calibrada a la salida del AD8232; autoescala)";
      app.querySelector("#estado-escala-vertical").textContent =
        `mV_OUT calibrados del ESP32: ${samples.length} muestras; línea base visual ${baseline.toFixed(1)} mV. ` +
        "No representa mV_ECG ni confirma exactitud metrológica; los ADC originales se conservan.";
    } else {
      app.querySelector("#unidad-eje").textContent =
        "ADC (cuentas; autoescala visual, no mV)";
      app.querySelector("#estado-escala-vertical").textContent =
        `Muestras originales: ${samples.length}; línea base visual ADC: ${baseline}; ` +
        `escala autoajustada solo para mostrar. No se dispone de mV_OUT calibrados. ` +
        `Muestras en rieles 0/4095: ${lowerRail}/${upperRail}.`;
    }
  }

  function updateSignalContinuityStatus(buffer) {
    app.querySelector("#estado-integridad-senal").textContent =
      `Interrupciones de comunicación representadas con trazos separados: ` +
      `${buffer.discontinuitiesCount}. El ESP32 no informa pérdidas internas entre muestras.`;
  }

  function liveSignalPath(
    buffer,
    samples = liveSignalSamples(buffer),
    scale = visualAmplitudeScale(samples)
  ) {
    const commands = [];
    for (let offset = 0; offset < buffer.size; offset += 1) {
      const position = (buffer.head + offset) % buffer.capacity;
      const sequence = buffer.sequences[position];
      const y = (GRAFICA_Y_INICIO + GRAFICA_Y_FIN) / 2 -
        ((buffer.samples[position] - scale.baseline) / scale.amplitude) *
          ((GRAFICA_Y_FIN - GRAFICA_Y_INICIO) / 2);
      const x = (sequence - buffer.lastSequence) * GRAFICA_PASO_X;
      commands.push(
        `${buffer.discontinuities[position] || offset === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`
      );
    }
    return commands.join(" ");
  }

  function liveSignalOffset(buffer, now) {
    if (buffer.size === 0) return GRAFICA_X_FIN;
    const ageSeconds = Math.max(0, (now - buffer.lastSampleReceivedAt) / 1000);
    return GRAFICA_X_FIN - ageSeconds * buffer.frequency * GRAFICA_PASO_X;
  }

  function updateLiveSignalTrace(now) {
    const trace = app.querySelector("#trazo-senal");
    const group = app.querySelector("#trazo-grupo");
    const samples = liveSignalSamples(liveSignalBuffer);
    const scale = visualAmplitudeScale(samples);
    trace.setAttribute(
      "d",
      liveSignalPath(liveSignalBuffer, samples, scale)
    );
    group.setAttribute(
      "transform",
      `translate(${liveSignalOffset(liveSignalBuffer, now).toFixed(2)} 0)`
    );
    updateSignalScaleStatus(samples, scale.baseline, liveSignalBuffer.unit);
    updateSignalContinuityStatus(liveSignalBuffer);
  }

  function animateLiveSignal() {
    if (liveSignalFrame !== null) return;
    const renderFrame = (now) => {
      liveSignalFrame = null;
      if (!isCapturing) return;
      app.querySelector("#trazo-grupo").setAttribute(
        "transform",
        `translate(${liveSignalOffset(liveSignalBuffer, now).toFixed(2)} 0)`
      );
      liveSignalFrame = window.requestAnimationFrame(renderFrame);
    };
    liveSignalFrame = window.requestAnimationFrame(renderFrame);
  }

  function stopLiveSignalAnimation() {
    if (liveSignalFrame !== null) {
      window.cancelAnimationFrame(liveSignalFrame);
      liveSignalFrame = null;
    }
    if (liveSignalBuffer.size > 0) updateLiveSignalTrace(performance.now());
  }

  function drawSignal(samples, unit = "ADC") {
    const trace = app.querySelector("#trazo-senal");
    if (samples.length === 0) {
      trace.setAttribute("d", "");
      app.querySelector("#trazo-grupo").setAttribute(
        "transform",
        `translate(${GRAFICA_X_FIN} 0)`
      );
      updateSignalScaleStatus([], 0, unit);
      return;
    }

    const visibleSamples = samples.slice(-MUESTRAS_VENTANA_VISUAL);
    const scale = visualAmplitudeScale(visibleSamples);
    const points = visibleSamples.map((sample, index) => {
      const x = index * GRAFICA_PASO_X;
      const y = (GRAFICA_Y_INICIO + GRAFICA_Y_FIN) / 2 -
        ((sample - scale.baseline) / scale.amplitude) *
          ((GRAFICA_Y_FIN - GRAFICA_Y_INICIO) / 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    });
    trace.setAttribute("d", points.join(" "));
    app.querySelector("#trazo-grupo").setAttribute(
      "transform",
      `translate(${GRAFICA_X_INICIO} 0)`
    );
    updateSignalScaleStatus(visibleSamples, scale.baseline, unit);
    app.querySelector("#estado-integridad-senal").textContent =
      "Captura guardada: no se agregaron muestras ni se interpolaron segmentos.";
    app.querySelector("#tiempo-medio").textContent = "5 s";
    app.querySelector("#tiempo-total").textContent =
      `${VENTANA_VISUAL_SEGUNDOS} s`;
  }

  function clearSignal() {
    resetLiveSignalBuffer(liveSignalBuffer, null);
    drawSignal([]);
    app.querySelector("#tiempo-medio").textContent = "— s";
    app.querySelector("#tiempo-total").textContent = "— s";
    app.querySelector("#cantidad-final").textContent = "—";
    app.querySelector("#frecuencia-final").textContent = "—";
    app.querySelector("#unidad-final").textContent = "—";
    updateSignalContinuityStatus(liveSignalBuffer);
  }

  function renderAssessmentList(selector, values, emptyMessage) {
    const list = app.querySelector(selector);
    const entries = Array.isArray(values) && values.length > 0
      ? values.map(String)
      : [emptyMessage];
    list.replaceChildren(...entries.map((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    }));
  }

  function renderRuleAssessments(rules) {
    const list = app.querySelector("#evaluacion-reglas");
    const validRules = Array.isArray(rules)
      ? rules.filter((rule) =>
        typeof rule?.identificador === "string" &&
        ["CUMPLE", "NO_CUMPLE", "NO_EVALUABLE"].includes(rule.estado) &&
        typeof rule.motivo === "string" &&
        rule.motivo.trim().length > 0
      )
      : [];
    const entries = validRules.length > 0
      ? validRules.map((rule) =>
        `${rule.identificador} · ${rule.estado}: ${rule.motivo}`
      )
      : ["El backend no devolvió resultados individuales por regla."];
    list.replaceChildren(...entries.map((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    }));
  }

  function renderPreventiveAssessment(result) {
    const identifiers = [
      "RC-ECG-001",
      "RC-ECG-002",
      "RC-ECG-003",
      "RC-ECG-004",
      "RC-ECG-005",
      "RC-ECG-006",
      "RC-ECG-007",
      "RC-ECG-008",
      "RC-ECG-009",
    ];
    const qualityReady = "APTA SEGÚN LOS CRITERIOS TÉCNICOS DE LA FICHA";
    const panel = app.querySelector("#evaluacion-preventiva");
    const assessment = result?.evaluacion_preventiva;
    const stateCards = app.querySelectorAll(".assessment-state");
    let matchingCard;
    let nonEvaluableCard;
    for (const card of stateCards) {
      if (
        matchingCard === undefined &&
        card.dataset.nivel === assessment?.nivel &&
        card.dataset.color === assessment?.color
      ) {
        matchingCard = card;
      }
      if (nonEvaluableCard === undefined && card.dataset.nivel === "NO_EVALUABLE") {
        nonEvaluableCard = card;
      }
    }
    const hasMeasurementData = assessment?.valores_medidos &&
      typeof assessment.valores_medidos === "object" &&
      !Array.isArray(assessment.valores_medidos);
    const reglasVerdesValidas = Array.isArray(assessment?.reglas) &&
      assessment.reglas.length === identifiers.length &&
      assessment.reglas.every((rule, index) =>
        rule?.identificador === identifiers[index] &&
        rule.estado === "CUMPLE" &&
        typeof rule.motivo === "string" &&
        rule.motivo.trim().length > 0
      );
    const calidadVerdeValida =
      assessment?.calidad_senal === qualityReady &&
      assessment?.parametros_evaluados?.length ===
        identifiers.length &&
      assessment.parametros_evaluados.every(
        (ruleId, index) => ruleId === identifiers[index]
      ) &&
      assessment?.parametros_no_evaluables?.length === 0 &&
      assessment?.criterios_activados?.length === 0 &&
      assessment?.datos_tecnicos?.frecuencia_muestreo_hz >= 500 &&
      (assessment.datos_tecnicos.cantidad_muestras - 1) /
        assessment.datos_tecnicos.frecuencia_muestreo_hz >= 10 &&
      assessment?.datos_tecnicos?.unidad === "mV";
    const hasCompleteAssessment =
      matchingCard !== undefined &&
      typeof assessment.motivo === "string" &&
      assessment.motivo.trim().length > 0 &&
      Array.isArray(assessment.parametros_evaluados) &&
      hasMeasurementData &&
      Array.isArray(assessment.criterios_activados) &&
      Array.isArray(assessment.parametros_no_evaluables) &&
      Array.isArray(assessment.advertencias_tecnicas) &&
      typeof assessment.calidad_senal === "string" &&
      assessment.calidad_senal.trim().length > 0 &&
      Number.isInteger(assessment.datos_tecnicos?.frecuencia_muestreo_hz) &&
      Number.isInteger(assessment.datos_tecnicos?.cantidad_muestras) &&
      ["mV", "ADC"].includes(assessment.datos_tecnicos?.unidad) &&
      (assessment.nivel !== "VERDE" ||
        (reglasVerdesValidas &&
          calidadVerdeValida &&
          Object.keys(assessment.valores_medidos).length > 0));
    const selectedCard = hasCompleteAssessment
      ? matchingCard
      : nonEvaluableCard;

    stateCards.forEach((card) => card.removeAttribute("aria-current"));
    selectedCard?.setAttribute("aria-current", "true");
    panel.dataset.color = selectedCard?.dataset.color.toLowerCase() ?? "gris";

    if (!hasCompleteAssessment) {
      app.querySelector("#evaluacion-nivel").textContent = "NO EVALUABLE · GRIS";
      app.querySelector("#evaluacion-motivo").textContent =
        "La API no proporcionó una evaluación preventiva compatible; no se puede inferir normalidad.";
      app.querySelector("#evaluacion-calidad").textContent = "NO EVALUADA";
      app.querySelector("#evaluacion-datos-tecnicos").textContent =
        "No disponibles.";
      renderAssessmentList(
        "#evaluacion-parametros-evaluados",
        [],
        "Ninguno."
      );
      renderAssessmentList(
        "#evaluacion-valores-medidos",
        [],
        "No hay mediciones clínicas confiables."
      );
      renderAssessmentList(
        "#evaluacion-criterios",
        [],
        "No se evaluaron criterios clínicos; esto no significa normalidad."
      );
      renderAssessmentList(
        "#evaluacion-parametros-pendientes",
        ["No se recibió una evaluación compatible."],
        "No se recibió una evaluación compatible."
      );
      renderAssessmentList(
        "#evaluacion-advertencias",
        [],
        "La evaluación clínica y la calidad de señal no están disponibles."
      );
      renderRuleAssessments([]);
      return;
    }

    app.querySelector("#evaluacion-nivel").textContent =
      `${assessment.nivel} · ${assessment.color}`;
    app.querySelector("#evaluacion-motivo").textContent = assessment.motivo;
    app.querySelector("#evaluacion-calidad").textContent =
      assessment.calidad_senal;
    const technical = assessment.datos_tecnicos;
    const metrics = assessment.metricas_tecnicas;
    app.querySelector("#evaluacion-datos-tecnicos").textContent =
      technical
        ? `${technical.cantidad_muestras} muestras · ${technical.frecuencia_muestreo_hz} Hz · ${technical.unidad}` +
          (metrics
            ? ` · intervalo entre muestras: ${metrics.duracion_entre_muestras_segundos.toFixed(3)} s · rango: ${metrics.amplitud_minima}–${metrics.amplitud_maxima} (${metrics.amplitud_rango}) · ${metrics.muestras_distintas} valores distintos` +
              (technical.unidad === "ADC"
                ? ` · muestras ADC en 0/4095: ${metrics.muestras_adc_en_riel_inferior}/${metrics.muestras_adc_en_riel_superior}`
                : "")
            : "")
        : "No disponibles.";
    renderAssessmentList(
      "#evaluacion-parametros-evaluados",
      assessment.parametros_evaluados,
      "Ninguno."
    );
    renderAssessmentList(
      "#evaluacion-valores-medidos",
      Object.entries(assessment.valores_medidos ?? {}).map(
        ([name, value]) => `${name}: ${value}`
      ),
      "No hay mediciones clínicas confiables."
    );
    renderAssessmentList(
      "#evaluacion-criterios",
      assessment.criterios_activados,
      "No se evaluaron criterios clínicos; esto no significa normalidad."
    );
    renderAssessmentList(
      "#evaluacion-parametros-pendientes",
      assessment.parametros_no_evaluables,
      "No se recibió una lista de parámetros no evaluables."
    );
    renderAssessmentList(
      "#evaluacion-advertencias",
      assessment.advertencias_tecnicas,
      "No se recibió una lista de advertencias técnicas."
    );
    renderRuleAssessments(assessment.reglas);
  }

  function actualizarCapturaGuardada(result, isNewCapture = false) {
    if (!capturaSensorValida(result)) {
      throw new Error("La API devolvió una captura física que no cumple el contrato ECG.");
    }
    renderPreventiveAssessment(result);
    const data = result.data;
    const muestrasGrafica = data.muestras;
    const unidadGrafica = "ADC";
    capturaActual = {
      adquisicion_id: data.adquisicion_id,
      frecuencia_muestreo_hz: data.frecuencia_muestreo_hz,
      muestras: [...data.muestras],
      unidad: data.unidad,
      muestras_mV_OUT: data.muestras_mV_OUT ? [...data.muestras_mV_OUT] : null,
    };
    drawSignal(muestrasGrafica, unidadGrafica);
    app.querySelector("#cantidad-final").textContent = String(capturaActual.muestras.length);
    app.querySelector("#frecuencia-final").textContent =
      `${capturaActual.frecuencia_muestreo_hz} Hz`;
    app.querySelector("#unidad-final").textContent = unidadGrafica === "mV_OUT"
      ? "ADC original conservado · mV_OUT calibrados"
      : data.estado_mV_OUT === "NO_CONFIABLE"
        ? "ADC original · mV_OUT recibido, pero no confiable"
        : "ADC original · mV_OUT no evaluable";
    app.querySelector("#origen-resumen").textContent =
      `Origen: SENSOR · ESP32 ${dispositivoEcg?.codigo ?? "ECG-001"} · resultado #${result.id}.`;
    app.querySelector("#descripcion-resumen").textContent =
      data.estado_mV_OUT === "NO_CONFIABLE"
        ? "La API conserva mV_OUT recibidos, pero no puede verificar su procedencia; la gráfica muestra ADC original. No equivale a mV_ECG ni constituye interpretación clínica."
        : "Captura ADC original recibida y guardada por la API. mV_OUT no evaluable; sin filtros ni identificación automática de ondas.";
    app.querySelector("#capturas-historicas").value = String(result.id);
    app.querySelector("#estado-guardado").textContent =
      `Resultado guardado: la API confirmó la captura #${result.id}.`;
    app.querySelector("#estado-captura").textContent = isNewCapture
      ? `Captura nueva confirmada y guardada (#${result.id}).`
      : `Captura histórica cargada (#${result.id}); no es una captura nueva.`;
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
    const unidadGrafica = "ADC";
    const samples = state.muestras;
    const stateForGraph = {
      ...state,
      muestras: samples,
      unidad: unidadGrafica,
    };
    if (samples.length > 0) {
      const changed = appendLiveSignalState(
        liveSignalBuffer,
        stateForGraph,
        performance.now()
      );
      if (changed) updateLiveSignalTrace(performance.now());
      animateLiveSignal();
      app.querySelector("#cantidad-final").textContent = String(samples.length);
      app.querySelector("#frecuencia-final").textContent =
        `${state.frecuencia_muestreo_hz} Hz`;
      app.querySelector("#unidad-final").textContent =
        state.estado_mV_OUT === "NO_CONFIABLE"
          ? "ADC original · mV_OUT recibido, pero no confiable"
          : "ADC original · mV_OUT no evaluable";
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
    stopLiveSignalAnimation();
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
      setDeviceConnection(
        state.backend_conectado ? "CONECTADO" : "ERROR",
        state.backend_conectado
          ? "ESP32 y FastAPI responden"
          : "el ESP32 perdió la comunicación mDNS con FastAPI"
      );
      if (state.adquisicion_id) acquisitionId = state.adquisicion_id;
      updateLiveSignal(state);

      if (!state.electrodos_conectados && state.adquisicion_en_curso) {
        finishWithError("el ESP32 detectó electrodos desconectados y abortó la captura.");
        return;
      }
      if (state.captura_pendiente) {
        app.querySelector("#estado-captura").textContent =
          "Adquisición completa (2500 muestras); esperando confirmación de persistencia.";
        if (state.codigo_http < 200 || state.codigo_http >= 300) {
          setStatus(`Error de guardado (${state.codigo_http || "red"}): ${state.mensaje} Se conserva la captura y el ESP32 reintentará con el mismo UUID.`);
          reportError(new Error(state.mensaje || "La API no confirmó el guardado."));
        } else {
          setStatus("Procesando y guardando la captura completa en la API…");
        }
      } else if (state.adquisicion_en_curso) {
        app.querySelector("#estado-captura").textContent =
          `Adquisición en curso: ${state.cantidad_muestras}/${MUESTRAS_CAPTURA}; aún no es una captura confirmada.`;
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
          app.querySelector("#estado-guardado").textContent =
            "No se confirmó un resultado guardado.";
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
      markLiveSignalDiscontinuity(liveSignalBuffer);
      setDeviceConnection("ERROR", "sin respuesta del ESP32 (red, CORS o timeout)");
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
      !dispositivoEcg || !Number.isSafeInteger(episodioActivo.id) ||
      estadoConexion !== "CONECTADO" || esp32BaseUrl === null
    ) return;

    const baseUrl = esp32BaseUrl;

    capturaActual = null;
    acquisitionId = null;
    sensorCapturesById = new Map();
    clearSignal();
    isCapturing = true;
    updateStartButton();
    showStep(currentStep, true);
    app.querySelector("#estado-guardado").textContent = "";
    setStatus("Conectando con ESP32 y verificando el episodio…");
    app.querySelector("#estado-captura").textContent =
      "Conectado; adquisición aún no iniciada.";
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
        app.querySelector("#estado-captura").textContent =
          "Adquisición iniciada; la captura aún no está confirmada.";
        setStatus("Adquiriendo ECG: esperando las primeras muestras del AD8232…");
      }
      app.querySelector("#error").hidden = true;
      await pollAcquisition(baseUrl, generation);
    } catch (error) {
      isCapturing = false;
      setDeviceConnection("ERROR", "no se pudo confirmar la conexión o el inicio");
      app.querySelector("#estado-captura").textContent =
        "No se confirmó una captura nueva.";
      updateStartButton();
      setStatus(`Error de comunicación o inicio: ${error.message}`);
      reportError(error);
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
  app.querySelector("#capturas-historicas").addEventListener("change", (event) => {
    const result = sensorCapturesById.get(Number(event.target.value));
    if (result) actualizarCapturaGuardada(result);
  });
  showStep(0);
  updateStartButton();
  void loadEpisodeContext();
  void pollDeviceConnection();
})();
