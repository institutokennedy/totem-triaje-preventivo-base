(function () {
  "use strict";

  const CODIGO_DISPOSITIVO = "OIDO-001";
  const NOMBRE_DISPOSITIVO = "Audiometría";
  const TIPO_DISPOSITIVO = "OIDO";

  // Frecuencias de estímulo en Hz (configurables; sin interpretación clínica).
  const FRECUENCIAS_HZ = [250, 500, 1000, 2000, 4000, 8000];
  const SIGUIENTE_URL = "/resumen";

  const DURACION_TONO_MS = 1500;
  const VOLUMEN = 0.1; // Ganancia digital; no equivale a un nivel calibrado en dB SPL.
  const VOLUMEN_REDUCIDO = 0.01; // -20 dB respecto al volumen habitual.
  const PAUSA_ENTRE_TONOS_MS = 800;
  const SONDEO_MS = 150;          // cada cuánto se consulta la respuesta del joystick

  const $ = (id) => document.getElementById(id);
  const raiz = $("oido-modulo");

  function obtenerEpisodioId() {
    const params = new URLSearchParams(window.location.search);
    const valor =
      params.get("episodio_id") ||
      (raiz && raiz.dataset.episodioId) ||
      sessionStorage.getItem("episodio_id");
    const id = parseInt(valor, 10);
    if (!Number.isInteger(id)) return null;
    sessionStorage.setItem("episodio_id", String(id));
    return id;
  }

  const estado = {
    episodioId: obtenerEpisodioId(),
    dispositivoId: null,
    cursor: 0,
    indice: 0,
    estimulos: [],
    ensayos: [],
    porJoystick: 0,
    porManual: 0,
    audio: null,
    resolver: null,
    errorRed: false,
    formulario: null,
    nivelSenal: "NORMAL",
  };

  function mensaje(texto, esError) {
    const el = $("oido-mensaje");
    el.textContent = texto || "";
    el.className = esError ? "error" : "";
  }

  function mostrar(paso) {
    ["paso-formulario", "paso-instrucciones", "paso-medicion", "paso-resumen"].forEach((id) => {
      $(id).hidden = id !== paso;
    });
  }

  const pausa = (ms) => new Promise((r) => setTimeout(r, ms));

  // -------------------------------------------------------------- formulario
  // Todas las casillas son opcionales: "Continuar" siempre está disponible.
  function actualizarOpcionesProblema() {
    const marcado = $("chk-problema").checked;
    $("opciones-problema").hidden = !marcado;
    $("chk-problema").setAttribute("aria-expanded", String(marcado));
    if (!marcado) {
      document.querySelectorAll('input[name="problema"]').forEach((c) => {
        c.checked = false;
      });
      actualizarCampoOtro();
    }
  }

  function actualizarCampoOtro() {
    const marcado = $("chk-otro").checked;
    $("campo-otro").hidden = !marcado;
    if (marcado) {
      $("txt-otro").focus();
    } else {
      $("txt-otro").value = "";
    }
  }

  function valoresMarcados(nombre) {
    return Array.from(document.querySelectorAll('input[name="' + nombre + '"]:checked')).map(
      (c) => c.value
    );
  }

  function continuarDesdeFormulario() {
    const problemasAuditivos = valoresMarcados("problema");
    estado.formulario = {
      tiene_problema_auditivo: $("chk-problema").checked,
      problemas_auditivos: problemasAuditivos,
      otro_problema: $("txt-otro").value.trim(),
      factores: valoresMarcados("factor"),
    };
    const reportaProblemaAuditivo =
      estado.formulario.tiene_problema_auditivo || problemasAuditivos.length > 0;
    estado.nivelSenal = reportaProblemaAuditivo
      ? "REDUCIDO_POR_AUTOINFORME"
      : "NORMAL";
    $("aviso-volumen-reducido").hidden = !reportaProblemaAuditivo;
    try {
      sessionStorage.setItem("oido_formulario", JSON.stringify(estado.formulario));
    } catch (_) {
      /* sin almacenamiento: se continúa igual */
    }
    mostrar("paso-instrucciones");
  }

  // ------------------------------------------------------------- dispositivo
  function idDe(disp) {
    return disp.id_dispositivo !== undefined ? disp.id_dispositivo : disp.id;
  }

  async function obtenerDispositivoId() {
    const resp = await fetch("/api/v1/dispositivos");
    if (!resp.ok) throw new Error("No se pudo consultar la lista de dispositivos");
    const lista = await resp.json();
    const items = Array.isArray(lista) ? lista : lista.items || [];
    let disp = items.find((d) => d.codigo === CODIGO_DISPOSITIVO);

    if (!disp) {
      const creado = await fetch("/api/v1/dispositivos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          codigo: CODIGO_DISPOSITIVO,
          nombre: NOMBRE_DISPOSITIVO,
          tipo: TIPO_DISPOSITIVO,
        }),
      });
      if (!creado.ok) {
        throw new Error("No se pudo registrar el dispositivo " + CODIGO_DISPOSITIVO);
      }
      disp = await creado.json();
    }

    const id = idDe(disp);
    if (id === undefined) throw new Error("El dispositivo no tiene identificador");
    return id;
  }

  // ------------------------------------------------------------------ audio
  function prepararAudio() {
    const Contexto = window.AudioContext || window.webkitAudioContext;
    if (!Contexto) throw new Error("Este navegador no permite reproducir audio");
    if (!estado.audio) estado.audio = new Contexto();
    if (typeof estado.audio.createStereoPanner !== "function") {
      throw new Error("Este navegador no permite separar el audio en estéreo");
    }
    return estado.audio.state === "suspended" ? estado.audio.resume() : Promise.resolve();
  }

  // Reproduce el tono en un solo canal (derecho +1, izquierdo -1).
  function reproducirTono(frecuenciaHz, oidoIdx) {
    const ctx = estado.audio;
    const osc = ctx.createOscillator();
    const ganancia = ctx.createGain();
    const duracion = DURACION_TONO_MS / 1000;
    const t = ctx.currentTime;

    osc.type = "sine";
    osc.frequency.value = frecuenciaHz;
    ganancia.gain.setValueAtTime(0, t);
    const volumen = estado.nivelSenal === "REDUCIDO_POR_AUTOINFORME"
      ? VOLUMEN_REDUCIDO
      : VOLUMEN;
    ganancia.gain.linearRampToValueAtTime(volumen, t + 0.05);
    ganancia.gain.setValueAtTime(volumen, t + duracion - 0.05);
    ganancia.gain.linearRampToValueAtTime(0, t + duracion);

    osc.connect(ganancia);
    const panner = ctx.createStereoPanner();
    panner.pan.value = oidoIdx === 0 ? 1 : -1;
    ganancia.connect(panner);
    panner.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + duracion);
  }

  // ---------------------------------------------------- respuestas del joystick
  async function consultarRespuestas() {
    const resp = await fetch(
      "/api/v1/oido/respuestas/" + estado.dispositivoId + "?despues_de=" + estado.cursor
    );
    if (!resp.ok) throw new Error("sondeo " + resp.status);
    return resp.json(); // { ultimo, respuestas: [{ seq, respuesta, ... }] }
  }

  function normalizarLado(valor) {
    if (valor === "IZQUIERDO" || valor === "DERECHO" || valor === "NO_ESCUCHE") {
      return valor;
    }
    if (valor === true) return "DERECHO";
    if (valor === false) return "IZQUIERDO";
    throw new Error("El joystick envió una respuesta desconocida");
  }

  // Descarta cualquier respuesta anterior al inicio del estímulo.
  async function sincronizarCursor() {
    const datos = await consultarRespuestas();
    estado.cursor = datos.ultimo;
  }

  // Espera la primera respuesta nueva: del joystick (por la API) o del respaldo manual.
  function esperarRespuesta() {
    return new Promise((resolve) => {
      let activo = true;
      let consultando = false;

      const terminar = (valor, fuente) => {
        if (!activo) return;
        activo = false;
        clearInterval(temporizador);
        estado.resolver = null;
        resolve({ valor: valor, fuente: fuente });
      };
      estado.resolver = (valor) => terminar(valor, "manual");

      const temporizador = setInterval(async () => {
        if (!activo || consultando) return;
        consultando = true;
        try {
          const datos = await consultarRespuestas();
          if (estado.errorRed) {
            estado.errorRed = false;
            mensaje("");
          }
          if (activo && datos.respuestas.length > 0) {
            estado.cursor = datos.ultimo; // descarta respuestas extra
            terminar(normalizarLado(datos.respuestas[0].respuesta), "joystick");
          }
        } catch (_) {
          estado.errorRed = true;
          mensaje("Sin conexión con el servidor. Reintentando...", true);
        } finally {
          consultando = false;
        }
      }, SONDEO_MS);
    });
  }

  // ------------------------------------------------------------------ prueba
  function crearOrdenEstimulos() {
    const estimulos = FRECUENCIAS_HZ.flatMap((frecuencia_hz) => [
      { frecuencia_hz, lado_estimulo: "IZQUIERDO" },
      { frecuencia_hz, lado_estimulo: "DERECHO" },
    ]);
    for (let i = estimulos.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [estimulos[i], estimulos[j]] = [estimulos[j], estimulos[i]];
    }
    return estimulos;
  }

  function reiniciar() {
    estado.indice = 0;
    estado.estimulos = crearOrdenEstimulos();
    estado.ensayos = [];
    estado.porJoystick = 0;
    estado.porManual = 0;
    $("progreso-total").textContent = String(estado.estimulos.length);
    $("tabla-respuestas").querySelector("tbody").innerHTML = "";
    $("estado-respuesta").textContent = "";
    $("btn-confirmar").disabled = false;
    mensaje("");
  }

  function actualizarEstimulo() {
    $("frecuencia-actual").textContent = String(estado.estimulos[estado.indice].frecuencia_hz);
    $("progreso-actual").textContent = String(estado.indice + 1);
  }

  async function ejecutarPrueba() {
    for (let i = 0; i < estado.estimulos.length; i++) {
      estado.indice = i;
      const estimulo = estado.estimulos[i];
      actualizarEstimulo();
      $("estado-respuesta").textContent = "Escuche el tono y responda con el joystick...";

      await sincronizarCursor();
      reproducirTono(estimulo.frecuencia_hz, estimulo.lado_estimulo === "DERECHO" ? 0 : 1);
      const respuesta = await esperarRespuesta();

      estado.ensayos.push({
        frecuencia_hz: estimulo.frecuencia_hz,
        lado_estimulo: estimulo.lado_estimulo,
        respuesta: respuesta.valor,
      });
      if (respuesta.fuente === "manual") estado.porManual += 1;
      else estado.porJoystick += 1;

      $("estado-respuesta").textContent = "Respuesta registrada.";
      await pausa(PAUSA_ENTRE_TONOS_MS);
    }
    renderResumen();
    mostrar("paso-resumen");
  }

  async function comenzar() {
    const boton = $("btn-comenzar");
    boton.disabled = true;
    reiniciar();
    try {
      if (estado.dispositivoId === null) {
        estado.dispositivoId = await obtenerDispositivoId();
      }
      await prepararAudio();
      mostrar("paso-medicion");
      await ejecutarPrueba();
    } catch (err) {
      mensaje("Error: " + err.message, true);
      mostrar("paso-instrucciones");
    } finally {
      boton.disabled = false;
    }
  }

  function textoLado(valor) {
    return {
      IZQUIERDO: "Izquierda",
      DERECHO: "Derecha",
      NO_ESCUCHE: "No escuché",
    }[valor] || "Sin respuesta";
  }

  function renderResumen() {
    const tbody = $("tabla-respuestas").querySelector("tbody");
    tbody.innerHTML = "";
    estado.ensayos.forEach((ensayo) => {
      const tr = document.createElement("tr");
      [
        String(ensayo.frecuencia_hz),
        textoLado(ensayo.lado_estimulo),
        textoLado(ensayo.respuesta),
      ].forEach((texto) => {
        const td = document.createElement("td");
        td.textContent = texto;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function origenDeLosDatos() {
    if (estado.porManual === 0) return "ESP32";
    if (estado.porJoystick === 0) return "MANUAL";
    return "MIXTO";
  }

  async function confirmar() {
    const btn = $("btn-confirmar");
    btn.disabled = true;
    mensaje("Guardando resultados...");
    try {
      if (estado.dispositivoId === null) {
        estado.dispositivoId = await obtenerDispositivoId();
      }
      const resp = await fetch("/api/v1/oido/resultados", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          episodio_id: estado.episodioId,
          dispositivo_id: estado.dispositivoId,
          origen: origenDeLosDatos(),
          data: {
            ensayos: estado.ensayos,
            nivel_senal: estado.nivelSenal,
            cuestionario: estado.formulario,
          },
        }),
      });
      if (resp.status === 201) {
        mensaje("Resultados guardados correctamente.");
        window.location.href = SIGUIENTE_URL + "?episodio_id=" + estado.episodioId;
        return;
      }
      throw new Error("El servidor respondió con estado " + resp.status);
    } catch (err) {
      mensaje("Error: " + err.message, true);
      btn.disabled = false;
    }
  }

  function repetir() {
    // Reinicia los datos locales sin enviar nada al servidor.
    reiniciar();
    mostrar("paso-instrucciones");
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (estado.episodioId === null) {
      mensaje("No hay un episodio activo. Regrese al inicio.", true);
      $("btn-continuar").disabled = true;
      $("btn-comenzar").disabled = true;
      return;
    }
    $("progreso-total").textContent = String(FRECUENCIAS_HZ.length * 2);
    $("chk-problema").addEventListener("change", actualizarOpcionesProblema);
    $("chk-otro").addEventListener("change", actualizarCampoOtro);
    $("btn-continuar").addEventListener("click", continuarDesdeFormulario);
    $("btn-comenzar").addEventListener("click", comenzar);
    $("btn-izquierdo").addEventListener(
      "click",
      () => estado.resolver && estado.resolver("IZQUIERDO")
    );
    $("btn-derecho").addEventListener(
      "click",
      () => estado.resolver && estado.resolver("DERECHO")
    );
    $("btn-no-escuche").addEventListener(
      "click",
      () => estado.resolver && estado.resolver("NO_ESCUCHE")
    );
    $("btn-repetir").addEventListener("click", repetir);
    $("btn-confirmar").addEventListener("click", confirmar);
  });
})();