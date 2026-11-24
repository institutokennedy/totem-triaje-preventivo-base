(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);
  const episodioEnRuta = window.location.pathname.match(/\/episodios\/(\d+)\/resumen\/?$/);
  const episodioId = Number(
    params.get("episodio_id") ||
      (episodioEnRuta && episodioEnRuta[1]) ||
      sessionStorage.getItem("episodio_id")
  );

  function mostrarError(texto) {
    const nodo = el("mensaje-error");
    nodo.textContent = texto;
    nodo.hidden = !texto;
  }

  async function solicitar(url, opciones, mensajeError) {
    let respuesta;
    try {
      respuesta = await fetch(url, opciones);
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("La solicitud se canceló antes de completar.");
      }
      throw new Error(
        "No se pudo conectar con el servidor. Comprueba que la aplicación siga ejecutándose y vuelve a intentar."
      );
    }

    if (!respuesta.ok) {
      let detalle = "";
      try {
        const cuerpo = await respuesta.json();
        detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : "";
      } catch (_) {
        detalle = "";
      }
      throw new Error(
        detalle || `${mensajeError} (HTTP ${respuesta.status}).`
      );
    }
    return respuesta;
  }

  function llenarLista(idLista, items, clase, vacio) {
    const lista = el(idLista);
    lista.replaceChildren();
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "vacio";
      li.textContent = vacio;
      lista.appendChild(li);
      return;
    }
    items.forEach((nombre) => {
      const li = document.createElement("li");
      li.className = clase;
      li.textContent = nombre;
      lista.appendChild(li);
    });
  }

  async function cargarEstadoIA() {
    const nodo = el("estado-configuracion-ia");
    try {
      const respuesta = await solicitar(
        "/api/v1/analisis-ia/estado",
        undefined,
        "No se pudo consultar la configuración"
      );
      const estado = await respuesta.json();
      nodo.textContent = estado.habilitada
        ? `Disponible (${estado.modelo}). El análisis se ejecutará al generar el informe. El resultado es orientativo.`
        : "No configurada. El informe podrá generarse sin análisis asistido por IA.";
      nodo.classList.toggle("activa", estado.habilitada);
    } catch (error) {
      nodo.textContent = error.message;
      nodo.classList.add("error");
    }
  }

  async function cargarResumen() {
    mostrarError("");
    if (!episodioId) {
      mostrarError("No hay un episodio activo.");
      return;
    }
    try {
      const r = await solicitar(
        `/api/v1/episodios/${episodioId}/resumen`,
        undefined,
        "No se pudo cargar el resumen del episodio"
      );
      const datos = await r.json();
      const p = datos.paciente || {};
      const e = datos.episodio || {};
      const nombre = [p.nombre, p.apellido].filter(Boolean).join(" ") || "Paciente sin nombre";
      const estado = e.estado || "ABIERTO";
      el("datos-paciente").textContent = nombre;
      el("paciente-avatar").textContent = nombre
        .split(/\s+/)
        .slice(0, 2)
        .map((parte) => parte.charAt(0).toUpperCase())
        .join("");
      el("meta-episodio").textContent =
        `Episodio ${episodioId} · ${e.tipo_circuito || "Atención preventiva"}`;
      const insignia = el("estado-episodio");
      insignia.textContent = estado === "CERRADO" ? "Cerrado" : "En curso";
      insignia.classList.toggle("cerrado", estado === "CERRADO");
      const completados = datos.modulos_completados || [];
      const pendientes = datos.modulos_pendientes || [];
      llenarLista("lista-completados", completados, "hecho", "Aún no hay módulos completados");
      llenarLista("lista-pendientes", pendientes, "pendiente", "No hay módulos pendientes");
      const total = completados.length + pendientes.length || 6;
      const porcentaje = Math.round((completados.length / total) * 100);
      el("progreso-texto").textContent = `${completados.length} de ${total} módulos`;
      el("progreso-barra").setAttribute("aria-valuemax", String(total));
      el("progreso-barra").setAttribute("aria-valuenow", String(completados.length));
      el("progreso-valor").style.width = `${porcentaje}%`;
      el("btn-cerrar").disabled = estado === "CERRADO";
    } catch (error) {
      mostrarError(error.message);
    }
  }

  async function generarInforme() {
    mostrarError("");
    const boton = el("btn-generar");
    const textoOriginal = boton.textContent.trim();
    const estado = el("estado-generacion");
    boton.disabled = true;
    boton.setAttribute("aria-busy", "true");
    boton.textContent = "Generando informe…";
    estado.textContent = "Preparando el informe. Esto puede tardar unos segundos.";
    try {
      const r = await solicitar(
        `/api/v1/episodios/${episodioId}/informes`,
        { method: "POST" },
        "No se pudo generar el informe"
      );
      if (r.status !== 201) {
        throw new Error(`El servidor respondió con un estado inesperado (HTTP ${r.status}).`);
      }
      const informe = await r.json();
      el("leyenda-informe").textContent = informe.contenido.leyenda;
      el("estado-analisis-ia").textContent = informe.contenido.analisis_ia
        ? "El análisis asistido por IA es orientativo y requiere revisión profesional."
        : "Análisis asistido por IA no disponible; el triaje permanece pendiente de revisión profesional.";
      const base = `/api/v1/episodios/${episodioId}/informes/${informe.id}`;
      el("enlace-html").href = `${base}/html`;
      el("enlace-pdf").href = `${base}/html`;
      el("seccion-informe").hidden = false;
      estado.textContent = "Informe generado. Cargando vista previa…";
      el("vista-informe").onload = () => {
        estado.textContent = "Informe generado y vista previa lista.";
      };
      el("vista-informe").src = `${base}/html`;
      el("seccion-informe").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      mostrarError(e.message);
      estado.textContent = "No se pudo completar la generación del informe.";
    } finally {
      boton.disabled = false;
      boton.removeAttribute("aria-busy");
      boton.textContent = textoOriginal;
    }
  }

  async function cerrarEpisodio() {
    mostrarError("");
    if (!window.confirm("¿Cerrar el episodio? No podrá agregar más mediciones.")) return;
    try {
      await solicitar(
        `/api/v1/episodios/${episodioId}/cerrar`,
        { method: "POST" },
        "No se pudo cerrar el episodio"
      );
    } catch (error) {
      mostrarError(error.message);
      return;
    }
    sessionStorage.removeItem("episodio_id");
    window.location.assign("/");
  }

  el("btn-generar").addEventListener("click", generarInforme);
  el("btn-cerrar").addEventListener("click", cerrarEpisodio);
  if (!episodioId) {
    el("btn-generar").disabled = true;
    el("btn-cerrar").disabled = true;
  }
  cargarEstadoIA();
  cargarResumen();
})();