(function () {
  "use strict";

  const CODIGO_DISPOSITIVO = "OIDO-001";
  const NOMBRE_DISPOSITIVO = "Audiometría";
  const TIPO_DISPOSITIVO = "OIDO";

  // Frecuencias de estímulo en Hz (configurables; sin interpretación clínica).
  const FRECUENCIAS_HZ = [250, 500, 1000, 2000, 4000, 8000];
  const OIDOS = ["derecho", "izquierdo"]; // el orden define el canal: 0 = derecho, 1 = izquierdo
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
    oidoIdx: 0,
    derecho: [],
    izquierdo: [],
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
    return estado.audio.state === "suspended" ? estado.audio.resume() : Promise.resolve();
  }

  // Reproduce un tono senoidal solo en el canal del oído evaluado (derecho +1, izquierdo -1).
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
    if (ctx.createStereoPanner) {
      const panner = ctx.createStereoPanner();
      panner.pan.value = oidoIdx === 0 ? 1 : -1;
      ganancia.connect(panner);
      panner.connect(ctx.destination);
    } else {
      ganancia.connect(ctx.destination);
    }
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
            terminar(datos.respuestas[0].respuesta, "joystick");
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
  function reiniciar() {
    estado.indice = 0;
    estado.oidoIdx = 0;
    estado.derecho = [];
    estado.izquierdo = [];
    estado.porJoystick = 0;
    estado.porManual = 0;
    $("progreso-total").textContent = String(FRECUENCIAS_HZ.length * OIDOS.length);
    $("tabla-respuestas").querySelector("tbody").innerHTML = "";
    $("estado-respuesta").textContent = "";
    $("btn-confirmar").disabled = false;
    mensaje("");
  }

  function actualizarEstimulo() {
    $("oido-actual").textContent = OIDOS[estado.oidoIdx];
    $("frecuencia-actual").textContent = String(FRECUENCIAS_HZ[estado.indice]);
    $("progreso-actual").textContent = String(
      estado.oidoIdx * FRECUENCIAS_HZ.length + estado.indice + 1
    );
  }

  async function ejecutarPrueba() {
    for (let o = 0; o < OIDOS.length; o++) {
      for (let i = 0; i < FRECUENCIAS_HZ.length; i++) {
        estado.oidoIdx = o;
        estado.indice = i;
        actualizarEstimulo();
        $("estado-respuesta").textContent = "Escuche el sonido y responda con el joystick...";

        await sincronizarCursor();
        reproducirTono(FRECUENCIAS_HZ[i], o); // no se espera: puede responder durante el tono
        const r = await esperarRespuesta();

        (o === 0 ? estado.derecho : estado.izquierdo).push(r.valor);
        if (r.fuente === "manual") estado.porManual += 1;
        else estado.porJoystick += 1;

        $("estado-respuesta").textContent = r.valor
          ? "Respuesta recibida: sí escucha"
          : "Respuesta recibida: no escucha";
        await pausa(PAUSA_ENTRE_TONOS_MS);
      }
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

  function textoRespuesta(valor) {
    return valor ? "Sí escucha" : "No escucha";
  }

  function renderResumen() {
    const tbody = $("tabla-respuestas").querySelector("tbody");
    tbody.innerHTML = "";
    FRECUENCIAS_HZ.forEach((f, i) => {
      const tr = document.createElement("tr");
      [String(f), textoRespuesta(estado.derecho[i]), textoRespuesta(estado.izquierdo[i])].forEach(
        (t) => {
          const td = document.createElement("td");
          td.textContent = t;
          tr.appendChild(td);
        }
      );
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
            frecuencias_hz: FRECUENCIAS_HZ,
            resultados_oido_derecho: estado.derecho,
            resultados_oido_izquierdo: estado.izquierdo,
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
    $("progreso-total").textContent = String(FRECUENCIAS_HZ.length * OIDOS.length);
    $("chk-problema").addEventListener("change", actualizarOpcionesProblema);
    $("chk-otro").addEventListener("change", actualizarCampoOtro);
    $("btn-continuar").addEventListener("click", continuarDesdeFormulario);
    $("btn-comenzar").addEventListener("click", comenzar);
    $("btn-escuche").addEventListener("click", () => estado.resolver && estado.resolver(true));
    $("btn-no-escuche").addEventListener("click", () => estado.resolver && estado.resolver(false));
    $("btn-repetir").addEventListener("click", repetir);
    $("btn-confirmar").addEventListener("click", confirmar);
  });
})();