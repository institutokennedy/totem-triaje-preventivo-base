(() => {
  "use strict";

  const testApp = document.getElementById("circuito-prueba-app");
  if (testApp) {
    startTestMode(testApp);
    return;
  }

  const app = document.getElementById("circuito-app");
  if (!app) return;
  const message = app.querySelector("#mensaje");
  const radios = [...app.querySelectorAll('input[name="tipo_circuito"]')];
  for (const radio of radios) {
    radio.addEventListener("change", () => {
      if (radio.checked) {
        message.textContent = "Circuito " + radio.value + " seleccionado. La creación espera el paciente real del flujo de identificación.";
        message.setAttribute("role", "status");
      }
    });
  }

  function startTestMode(root) {
    const API = "/api/v1";
    const patientSelect = root.querySelector("#paciente-prueba");
    const createButton = root.querySelector("#crear-episodio-prueba");
    const createStatus = root.querySelector("#estado-episodio");
    const circuitRadios = [...root.querySelectorAll('input[name="tipo_circuito"]')];
    const captureButton = root.querySelector("#generar-ecg-prueba");
    const saveButton = root.querySelector("#guardar-ecg-prueba");
    const verifyButton = root.querySelector("#verificar-ecg-prueba");
    const saveAvailability = root.querySelector("#disponibilidad-guardado-prueba");
    let patients = new Map();
    let circuit = null;
    let episode = null;
    let device = null;
    let capture = null;
    let busy = false;
    let retryAllowed = true;
    let postConfirmed = false;
    let needsVerification = false;
    let savedId = null;

    function status(element, text, error = false) {
      element.textContent = text;
      element.setAttribute("role", error ? "alert" : "status");
      element.classList.toggle("error", error);
    }

    async function json(url, options) {
      const response = await fetch(url, options);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : "HTTP " + response.status;
        throw new Error(detail + " (" + response.status + ").");
      }
      return body;
    }

    function maskedDni(value) {
      const digits = String(value || "");
      return "DNI ••••" + digits.slice(-3);
    }

    function updateCreate() {
      createButton.disabled = busy || episode !== null ||
        !patients.has(Number(patientSelect.value)) ||
        (circuit !== "GUARDIA" && circuit !== "COMPLETO");
    }

    function updateSave() {
      saveButton.hidden = capture === null;
      saveButton.disabled = busy || episode === null || device === null ||
        capture === null || !retryAllowed || postConfirmed;
      verifyButton.hidden = !needsVerification || capture === null;
      verifyButton.disabled = busy;

      if (busy) {
        saveAvailability.textContent = "Procesando el guardado y verificando el resultado con la API…";
      } else if (episode === null) {
        saveAvailability.textContent = "Para guardar, primero creá y verificá un episodio de prueba.";
      } else if (device === null) {
        saveAvailability.textContent = "Guardado no disponible: no se verificó un dispositivo ECG activo y disponible.";
      } else if (capture === null) {
        saveAvailability.textContent = "Generá una señal simulada antes de guardar.";
      } else if (postConfirmed && !needsVerification) {
        saveAvailability.textContent = "La API confirmó y verificó esta captura. No es necesario volver a enviarla.";
      } else if (needsVerification) {
        saveAvailability.textContent = "El guardado espera la verificación de la consulta; no reenvíes esta captura.";
      } else if (!retryAllowed) {
        saveAvailability.textContent = "No se puede reintentar hasta verificar el estado del guardado.";
      } else {
        saveAvailability.textContent = "Episodio, dispositivo y señal verificados. La captura está lista para guardar.";
      }
    }

    async function loadPatients() {
      const message = root.querySelector("#estado-pacientes");
      try {
        const records = await json(API + "/pacientes", { headers: { Accept: "application/json" } });
        if (!Array.isArray(records)) throw new Error("La API no devolvió una lista de pacientes.");
        patientSelect.replaceChildren(new Option("Seleccioná un paciente existente…", ""));
        patients.clear();
        for (const item of records) {
          if (!Number.isSafeInteger(item.id) || item.id <= 0) continue;
          const patient = {
            id: item.id,
            nombre: item.nombre,
            apellido: item.apellido,
            dni: item.dni,
          };
          patients.set(patient.id, patient);
          const label = "#" + item.id + " · " + item.nombre + " " + item.apellido + " · " + maskedDni(item.dni);
          patientSelect.add(new Option(label, String(item.id)));
        }
        patientSelect.disabled = false;
        status(message, records.length
          ? "Elegí explícitamente un registro real. No se selecciona ningún paciente automáticamente."
          : "No hay pacientes registrados. Creá uno previamente desde Swagger para esta prueba.");
      } catch (error) {
        patientSelect.disabled = true;
        status(message, error.message || "No se pudieron consultar pacientes.", true);
      }
      updateCreate();
    }

    async function loadDevice() {
      const message = root.querySelector("#estado-dispositivo");
      try {
        const records = await json(API + "/dispositivos", { headers: { Accept: "application/json" } });
        if (!Array.isArray(records)) throw new Error("La API de dispositivos devolvió un formato inválido.");
        device = records.find((item) =>
          item.tipo === "ECG" &&
          item.activo === true && item.estado === "DISPONIBLE" &&
          Number.isSafeInteger(item.id) && item.id > 0
        ) || null;
        if (!device) throw new Error("No se encontró un dispositivo ECG activo y disponible. La señal se puede simular, pero no guardar.");
        status(message, "Dispositivo ECG disponible verificado: " + device.codigo + " (ID " + device.id + ").");
      } catch (error) {
        device = null;
        status(message, error.message || "No se pudo verificar el dispositivo ECG.", true);
      }
      updateSave();
    }

    async function createEpisode() {
      if (createButton.disabled) return;
      const patient = patients.get(Number(patientSelect.value));
      if (!patient || (circuit !== "GUARDIA" && circuit !== "COMPLETO")) return;
      busy = true;
      updateCreate();
      status(createStatus, "Creando episodio con el paciente real seleccionado…");
      try {
        const created = await json(API + "/episodios", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ paciente_id: patient.id, tipo_circuito: circuit }),
        });
        if (!Number.isSafeInteger(created.id) || created.id <= 0 ||
            created.paciente_id !== patient.id || created.tipo_circuito !== circuit) {
          throw new Error("La API no devolvió el episodio esperado; no se habilitó la captura.");
        }
        const checked = await json(API + "/episodios/" + created.id, { headers: { Accept: "application/json" } });
        if (checked.id !== created.id || checked.paciente_id !== patient.id || checked.tipo_circuito !== circuit) {
          throw new Error("No se pudo verificar el episodio creado; no se habilitó la captura.");
        }
        episode = checked;
        root.querySelector("#episodio-paciente").textContent =
          "#" + patient.id + " · " + patient.nombre + " " + patient.apellido + " · " + maskedDni(patient.dni);
        root.querySelector("#episodio-id-prueba").textContent = String(episode.id);
        root.querySelector("#episodio-circuito-prueba").textContent = episode.tipo_circuito;
        root.querySelector("#episodio-estado-prueba").textContent = episode.estado;
        root.querySelector("#resumen-episodio").hidden = false;
        root.querySelector("#seccion-ecg-prueba").hidden = false;
        status(createStatus, "Episodio #" + episode.id + " creado y consultado. Modo " + episode.tipo_circuito + ".");
        await loadDevice();
      } catch (error) {
        status(createStatus, error.message || "No se pudo crear o verificar el episodio.", true);
      } finally {
        busy = false;
        updateCreate();
        updateSave();
      }
    }

    function draw(samples) {
      const scale = Math.max(...samples.map((value) => Math.abs(value)), 1);
      const points = samples.map((value, index) => {
        const x = 24 + index * (592 / Math.max(samples.length - 1, 1));
        const y = 90 - (value / scale) * 68;
        return x + "," + y;
      });
      root.querySelector("#trazo-prueba").setAttribute("points", points.join(" "));
    }

    async function generateCapture() {
      if (!episode || busy) return;
      busy = true;
      captureButton.disabled = true;
      capture = null;
      retryAllowed = true;
      postConfirmed = false;
      needsVerification = false;
      savedId = null;
      root.querySelector("#resumen-captura").hidden = true;
      root.querySelector("#trazo-prueba").setAttribute("points", "");
      root.querySelector("#resultados-prueba").replaceChildren();
      root.querySelector("#resultados-prueba").hidden = true;
      root.querySelector("#estado-guardado-prueba").textContent = "";
      updateSave();
      try {
        const data = await json(API + "/ecg/simulador/captura", { headers: { Accept: "application/json" } });
        if (!Number.isInteger(data.frecuencia_muestreo_hz) || data.frecuencia_muestreo_hz <= 0 ||
            !Array.isArray(data.muestras) || !data.muestras.length ||
            !data.muestras.every((value) => typeof value === "number" && Number.isFinite(value)) ||
            (data.unidad !== "mV" && data.unidad !== "ADC")) {
          throw new Error("La respuesta del simulador no cumple el esquema técnico ECG.");
        }
        capture = {
          frecuencia_muestreo_hz: data.frecuencia_muestreo_hz,
          muestras: data.muestras,
          unidad: data.unidad,
        };
        root.querySelector("#cantidad-muestras").textContent = String(capture.muestras.length);
        root.querySelector("#frecuencia-muestras").textContent = capture.frecuencia_muestreo_hz + " Hz";
        root.querySelector("#unidad-muestras").textContent = capture.unidad;
        root.querySelector("#resumen-captura").hidden = false;
        draw(capture.muestras);
        status(root.querySelector("#estado-guardado-prueba"), "Señal simulada recibida. Todavía no se guardó.");
      } catch (error) {
        status(root.querySelector("#estado-guardado-prueba"), error.message || "Falló la simulación.", true);
      } finally {
        busy = false;
        captureButton.disabled = false;
        updateSave();
      }
    }

    function sameCapture(left, right) {
      return Boolean(left && right &&
        left.frecuencia_muestreo_hz === right.frecuencia_muestreo_hz &&
        left.unidad === right.unidad &&
        Array.isArray(left.muestras) && Array.isArray(right.muestras) &&
        left.muestras.length === right.muestras.length &&
        left.muestras.every((value, index) => value === right.muestras[index]));
    }

    async function getResults() {
      const response = await json(API + "/ecg/resultados/" + episode.id, { headers: { Accept: "application/json" } });
      if (response.episodio_id !== episode.id || response.modulo !== "ecg" ||
          !Array.isArray(response.resultados)) throw new Error("La consulta no coincide con el episodio.");
      return response.resultados;
    }

    function showResults(records) {
      const list = root.querySelector("#resultados-prueba");
      list.replaceChildren();
      for (const item of records) {
        const row = document.createElement("li");
        row.textContent = "Resultado #" + item.id + " · " + item.data.muestras.length +
          " muestras · " + item.data.frecuencia_muestreo_hz + " Hz · " + item.data.unidad;
        list.append(row);
      }
      list.hidden = records.length === 0;
    }

    async function verifySave() {
      if (!episode || !capture || busy) return;
      busy = true;
      updateSave();
      try {
        const records = await getResults();
        showResults(records);
        const match = records.find((item) => sameCapture(item.data, capture));
        needsVerification = false;
        if (match) {
          retryAllowed = false;
          status(root.querySelector("#estado-guardado-prueba"),
            postConfirmed && match.id === savedId
              ? "Guardado confirmado y verificado por la API. Resultado #" + match.id + "; origen SIMULADOR."
              : "Ya existe una captura idéntica (#" + match.id + "); no se reenvió para evitar duplicados.");
        } else if (postConfirmed) {
          needsVerification = true;
          retryAllowed = false;
          status(root.querySelector("#estado-guardado-prueba"),
            "El POST fue aceptado, pero la consulta todavía no encuentra el resultado. No se reintentó.");
        } else {
          retryAllowed = true;
          status(root.querySelector("#estado-guardado-prueba"),
            "La consulta no encontró esta captura; podés reintentar el guardado.");
        }
      } catch (error) {
        retryAllowed = false;
        needsVerification = true;
        status(root.querySelector("#estado-guardado-prueba"),
          "No se pudo verificar el estado; el reintento queda bloqueado. " + (error.message || ""), true);
      } finally {
        busy = false;
        updateSave();
      }
    }

    async function saveCapture() {
      if (busy) {
        status(root.querySelector("#estado-guardado-prueba"), "Ya hay una solicitud de guardado en curso.");
        return;
      }
      if (episode === null || device === null || capture === null || !retryAllowed || postConfirmed) {
        const reason = episode === null ? "falta un episodio verificado" :
          device === null ? "falta un dispositivo ECG activo y disponible" :
          capture === null ? "falta generar la señal simulada" :
          "el estado del guardado debe verificarse antes de reintentar";
        status(root.querySelector("#estado-guardado-prueba"), "No se inició el guardado: " + reason + ".", true);
        updateSave();
        return;
      }
      busy = true;
      updateSave();
      status(root.querySelector("#estado-guardado-prueba"), "Consultando resultados existentes antes de enviar la captura…");
      try {
        const existing = await getResults();
        showResults(existing);
        const duplicate = existing.find((item) => sameCapture(item.data, capture));
        if (duplicate) {
          retryAllowed = false;
          status(root.querySelector("#estado-guardado-prueba"),
            "Ya existe una captura idéntica (#" + duplicate.id + "); no se envió otro POST.");
          return;
        }
        const saved = await json(API + "/ecg/resultados", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({
            episodio_id: episode.id,
            dispositivo_id: device.id,
            origen: "SIMULADOR",
            data: capture,
          }),
        });
        if (!Number.isSafeInteger(saved.resultado_id) || saved.resultado_id <= 0) {
          throw new Error("La API no devolvió un resultado_id válido.");
        }
        postConfirmed = true;
        savedId = saved.resultado_id;
        retryAllowed = false;
        needsVerification = true;
        status(root.querySelector("#estado-guardado-prueba"),
          "POST aceptado (#" + savedId + "). Consultando el resultado persistido…");
      } catch (error) {
        postConfirmed = false;
        retryAllowed = false;
        needsVerification = true;
        status(root.querySelector("#estado-guardado-prueba"),
          "No se confirmó el POST: " + (error.message || "error de API") +
          ". Consultando antes de habilitar otro intento…", true);
      } finally {
        busy = false;
        updateSave();
      }
      if (needsVerification) await verifySave();
    }

    patientSelect.addEventListener("change", updateCreate);
    for (const radio of circuitRadios) {
      radio.addEventListener("change", () => {
        if (radio.checked) circuit = radio.value;
        updateCreate();
      });
    }
    createButton.addEventListener("click", createEpisode);
    captureButton.addEventListener("click", generateCapture);
    saveButton.addEventListener("click", saveCapture);
    verifyButton.addEventListener("click", verifySave);
    updateSave();
    void loadPatients();
  }
})();
