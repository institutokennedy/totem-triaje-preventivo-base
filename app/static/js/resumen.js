(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const raiz = $("resumen");
  const URL_INICIO = "/";

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

  const episodioId = obtenerEpisodioId();

  function mensaje(texto, esError) {
    const el = $("resumen-mensaje");
    el.textContent = texto || "";
    el.className = esError ? "error" : "";
  }

  function renderDl(idLista, objeto) {
    const dl = $(idLista);
    dl.innerHTML = "";
    Object.entries(objeto || {}).forEach(([k, v]) => {
      const dt = document.createElement("dt");
      dt.textContent = k;
      const dd = document.createElement("dd");
      dd.textContent = v === null || v === undefined ? "—" : String(v);
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
  }

  function renderLista(idLista, items, vacio) {
    const ul = $(idLista);
    ul.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.textContent = vacio;
      ul.appendChild(li);
      return;
    }
    items.forEach((t) => {
      const li = document.createElement("li");
      li.textContent = t;
      ul.appendChild(li);
    });
  }

  async function cargarResumen() {
    const resp = await fetch("/api/v1/episodios/" + episodioId + "/resumen");
    if (!resp.ok) throw new Error("No se pudo cargar el resumen (" + resp.status + ")");
    const data = await resp.json();
    renderDl("lista-paciente", data.paciente);
    renderDl("lista-episodio", data.episodio);
    renderLista("lista-completados", data.modulos_completados, "Ningún módulo realizado");
    renderLista("lista-pendientes", data.modulos_pendientes, "Sin módulos pendientes");
  }

  async function generarInforme() {
    const btn = $("btn-generar-informe");
    btn.disabled = true;
    mensaje("Generando informe...");
    try {
      const resp = await fetch("/api/v1/episodios/" + episodioId + "/informes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo_informe: "COMPLETO" }),
      });
      if (resp.status !== 201) throw new Error("El servidor respondió con estado " + resp.status);
      const informe = await resp.json();
      $("informe-version").textContent = String(informe.version);
      const contenido = informe.contenido_json || {};
      $("informe-leyenda").textContent = contenido.leyenda || "";
      $("informe-generado").hidden = false;
      mensaje("Informe generado correctamente.");
    } catch (err) {
      mensaje("Error: " + err.message, true);
    } finally {
      btn.disabled = false;
    }
  }

  async function finalizarEpisodio() {
    const btn = $("btn-finalizar");
    btn.disabled = true;
    try {
      const resp = await fetch("/api/v1/episodios/" + episodioId + "/finalizar", {
        method: "POST",
      });
      if (!resp.ok) throw new Error("El servidor respondió con estado " + resp.status);
      sessionStorage.removeItem("episodio_id");
      mensaje("Episodio finalizado.");
      window.location.href = URL_INICIO;
    } catch (err) {
      mensaje("Error: " + err.message, true);
      btn.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (episodioId === null) {
      mensaje("No hay un episodio activo.", true);
      $("btn-generar-informe").disabled = true;
      $("btn-finalizar").disabled = true;
      return;
    }
    $("btn-generar-informe").addEventListener("click", generarInforme);
    $("btn-finalizar").addEventListener("click", finalizarEpisodio);
    try {
      await cargarResumen();
    } catch (err) {
      mensaje("Error: " + err.message, true);
    }
  });
})();
