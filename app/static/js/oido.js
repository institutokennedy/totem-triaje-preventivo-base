(function () {
  "use strict";

  const CODIGO_DISPOSITIVO = "OIDO-001";
  // Frecuencias de estímulo (configurables; sin interpretación clínica).
  const FRECUENCIAS_HZ = [500, 1000, 2000, 4000];
  const OIDOS = ["derecho", "izquierdo"];
  const SIGUIENTE_URL = "/resumen";

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
    indice: 0,
    oidoIdx: 0,
    derecho: [],
    izquierdo: [],
  };

  function mensaje(texto, esError) {
    const el = $("oido-mensaje");
    el.textContent = texto || "";
    el.className = esError ? "error" : "";
  }

  function mostrar(paso) {
    ["paso-instrucciones", "paso-medicion", "paso-resumen"].forEach((id) => {
      $(id).hidden = id !== paso;
    });
  }

  async function obtenerDispositivoId() {
    const resp = await fetch("/api/v1/dispositivos");
    if (!resp.ok) throw new Error("No se pudo consultar la lista de dispositivos");
    const lista = await resp.json();
    const items = Array.isArray(lista) ? lista : lista.items || [];
    const disp = items.find((d) => d.codigo === CODIGO_DISPOSITIVO);
    if (!disp) throw new Error("Dispositivo " + CODIGO_DISPOSITIVO + " no encontrado");
    const id = disp.id_dispositivo !== undefined ? disp.id_dispositivo : disp.id;
    if (id === undefined) throw new Error("El dispositivo no tiene identificador");
    return id;
  }

  async function solicitarJson(url, opciones) {
    const resp = await fetch(url, opciones);
    const resultado = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detalle = resultado.detail || "No se pudo preparar la medición";
      throw new Error(typeof detalle === "string" ? detalle : JSON.stringify(detalle));
    }
    return resultado;
  }

  async function prepararEpisodioDemostracion() {
    const boton = $("btn-preparar-demo");
    boton.disabled = true;
    mensaje("Preparando episodio de demostración...");

    try {
      const pacientes = await solicitarJson("/api/v1/pacientes");
      let paciente = pacientes.find((item) => item.dni === "00000000");
      if (!paciente) {
        paciente = await solicitarJson("/api/v1/pacientes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dni: "00000000",
            nombre: "Paciente",
            apellido: "De demostración",
            fecha_nacimiento: "2000-01-01",
          }),
        });
      }

      const dispositivos = await solicitarJson("/api/v1/dispositivos");
      if (!dispositivos.some((item) => item.codigo === CODIGO_DISPOSITIVO)) {
        await solicitarJson("/api/v1/dispositivos", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            codigo: CODIGO_DISPOSITIVO,
            nombre: "Simulador auditivo",
            tipo: "OIDO",
          }),
        });
      }

      const episodio = await solicitarJson("/api/v1/episodios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paciente_id: paciente.id,
          tipo_circuito: "DEMOSTRACION_OIDO",
        }),
      });
      window.location.assign("/oido?episodio_id=" + encodeURIComponent(episodio.id));
    } catch (error) {
      mensaje("Error: " + error.message, true);
      boton.disabled = false;
    }
  }

  function reiniciar() {
    estado.indice = 0;
    estado.oidoIdx = 0;
    estado.derecho = [];
    estado.izquierdo = [];
    $("progreso-total").textContent = String(FRECUENCIAS_HZ.length * OIDOS.length);
    $("tabla-respuestas").querySelector("tbody").innerHTML = "";
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

  function comenzar() {
    reiniciar();
    mostrar("paso-medicion");
    actualizarEstimulo();
  }

  function registrarRespuesta(escucho) {
    (estado.oidoIdx === 0 ? estado.derecho : estado.izquierdo).push(escucho);
    estado.indice += 1;
    if (estado.indice >= FRECUENCIAS_HZ.length) {
      estado.indice = 0;
      estado.oidoIdx += 1;
    }
    if (estado.oidoIdx >= OIDOS.length) {
      renderResumen();
      mostrar("paso-resumen");
    } else {
      actualizarEstimulo();
    }
  }

  function textoRespuesta(valor) {
    return valor ? "Respuesta registrada" : "Sin respuesta";
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
          origen: "SIMULADOR",
          data: {
            frecuencias_hz: FRECUENCIAS_HZ,
            resultados_oido_derecho: estado.derecho,
            resultados_oido_izquierdo: estado.izquierdo,
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
      mensaje("Prepare un episodio de demostración para comenzar.");
      $("btn-comenzar").disabled = true;
      const botonDemo = $("btn-preparar-demo");
      if (botonDemo) botonDemo.addEventListener("click", prepararEpisodioDemostracion);
      return;
    }
    $("progreso-total").textContent = String(FRECUENCIAS_HZ.length * OIDOS.length);
    $("btn-comenzar").addEventListener("click", comenzar);
    $("btn-escuche").addEventListener("click", () => registrarRespuesta(true));
    $("btn-no-escuche").addEventListener("click", () => registrarRespuesta(false));
    $("btn-repetir").addEventListener("click", repetir);
    $("btn-confirmar").addEventListener("click", confirmar);
  });
})();