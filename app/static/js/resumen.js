(() => {
  "use strict";

  const el = (id) => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);
  const episodioId = Number(
    params.get("episodio_id") || sessionStorage.getItem("episodio_id")
  );

  function mostrarError(texto) {
    const nodo = el("mensaje-error");
    nodo.textContent = texto;
    nodo.hidden = !texto;
  }

  function llenarLista(idLista, items, clase, vacio) {
    const lista = el(idLista);
    lista.replaceChildren();
    if (!items.length) {
      const li = document.createElement("li");
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

  async function cargarResumen() {
    mostrarError("");
    if (!episodioId) {
      mostrarError("No hay un episodio activo.");
      return;
    }
    const r = await fetch(`/api/v1/episodios/${episodioId}/resumen`);
    if (!r.ok) {
      mostrarError("No se pudo cargar el resumen del episodio.");
      return;
    }
    const datos = await r.json();
    const p = datos.paciente || {};
    const e = datos.episodio || {};
    el("datos-paciente").textContent =
      `Paciente: ${p.nombre || "sin nombre"} (episodio ${episodioId})`;
    el("estado-episodio").textContent = `Estado del episodio: ${e.estado || "ABIERTO"}`;
    llenarLista("lista-completados", datos.modulos_completados, "hecho", "Ninguno todavía");
    llenarLista("lista-pendientes", datos.modulos_pendientes, "pendiente", "Ninguno");
    el("btn-cerrar").disabled = e.estado === "CERRADO";
  }

  async function generarInforme() {
    mostrarError("");
    const boton = el("btn-generar");
    boton.disabled = true;
    try {
      const r = await fetch(`/api/v1/episodios/${episodioId}/informes`, { method: "POST" });
      if (r.status !== 201) throw new Error("No se pudo generar el informe.");
      const informe = await r.json();
      el("leyenda-informe").textContent = informe.contenido.leyenda;
      const base = `/api/v1/episodios/${episodioId}/informes/${informe.id}`;
      el("enlace-html").href = `${base}/html`;
      el("enlace-pdf").href = `${base}/html`;
      el("vista-informe").src = `${base}/html`;
      el("seccion-informe").hidden = false;
    } catch (e) {
      mostrarError(e.message);
    } finally {
      boton.disabled = false;
    }
  }

  async function cerrarEpisodio() {
    mostrarError("");
    if (!window.confirm("¿Cerrar el episodio? No podrá agregar más mediciones.")) return;
    const r = await fetch(`/api/v1/episodios/${episodioId}/cerrar`, { method: "POST" });
    if (!r.ok) {
      mostrarError("No se pudo cerrar el episodio.");
      return;
    }
    sessionStorage.removeItem("episodio_id");
    window.location.assign("/");
  }

  el("btn-generar").addEventListener("click", generarInforme);
  el("btn-cerrar").addEventListener("click", cerrarEpisodio);
  cargarResumen();
})();