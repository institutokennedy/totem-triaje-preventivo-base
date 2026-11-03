(function () {
  "use strict";

  const ETIQUETAS = {
    signos_vitales: "Signos Vitales",
    ecg: "ECG",
    glucemia: "Glucemia",
    boca: "Boca",
    vista: "Vista",
    oido: "Oído",
  };

  function obtenerEpisodioId() {
    const el = document.querySelector("[data-episodio-id]");
    if (el && el.dataset.episodioId) return el.dataset.episodioId;
    const params = new URLSearchParams(window.location.search);
    const q = params.get("episodio_id");
    if (q) return q;
    const m = window.location.pathname.match(/episodios\/(\d+)/);
    if (m) return m[1];
    try {
      return sessionStorage.getItem("episodio_id");
    } catch (_) {
      return null;
    }
  }

  const episodioId = obtenerEpisodioId();
  const $ = (id) => document.getElementById(id);
  const mensaje = (txt, error) => {
    const el = $("mensaje");
    el.textContent = txt;
    el.style.color = error ? "#c62828" : "#2e7d32";
  };

  function etiqueta(m) {
    return ETIQUETAS[m] || m;
  }

  function formatearFecha(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("es-AR");
  }

  function renderFicha(d) {
    $("paciente-nombre").textContent = d.paciente_nombre || "—";
    $("paciente-dni").textContent = d.paciente_dni || "—";
    $("episodio-id").textContent = d.episodio_id;
    $("circuito").textContent = d.circuito || "—";
    $("estado-episodio").textContent = d.estado_episodio || "—";
    const c = d.clasificacion;
    $("clasificacion").textContent = c
      ? c.nivel || c.clasificacion || c.prioridad || JSON.stringify(c)
      : "Sin clasificar";
    if (d.advertencia_legal) $("advertencia-legal").textContent = d.advertencia_legal;
  }

  function renderTimeline(detalles) {
    const ol = $("timeline");
    ol.innerHTML = "";
    detalles.forEach((det) => {
      const li = document.createElement("li");
      li.className = det.completado ? "ok" : "";
      const fecha = det.completado ? " — " + formatearFecha(det.fecha_hora) : " — pendiente";
      li.textContent = etiqueta(det.modulo) + fecha;
      ol.appendChild(li);
    });
  }

  function renderCards(detalles) {
    const cont = $("cards-modulos");
    cont.innerHTML = "";
    detalles.forEach((det) => {
      const card = document.createElement("article");
      card.className = "card " + (det.completado ? "completado" : "pendiente");

      const h = document.createElement("h3");
      h.textContent = etiqueta(det.modulo);
      card.appendChild(h);

      const p = document.createElement("p");
      p.textContent = det.completado ? "✔ Completado" : "○ Pendiente";
      card.appendChild(p);

      if (det.completado && det.data) {
        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(det.data, null, 2);
        card.appendChild(pre);
      }
      cont.appendChild(card);
    });
  }

  async function cargarTrazabilidad() {
    try {
      const r = await fetch(`/api/v1/episodios/${episodioId}/trazabilidad`);
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      const d = await r.json();
      renderFicha(d);
      renderTimeline(d.detalles);
      renderCards(d.detalles);
    } catch (e) {
      mensaje("No se pudo cargar la trazabilidad: " + e.message, true);
    }
  }

  async function generarInforme() {
    const btn = $("btn-generar");
    btn.disabled = true;
    try {
      const r = await fetch(`/api/v1/episodios/${episodioId}/informes`, {
        method: "POST",
      });
      if (r.status !== 201) throw new Error((await r.json()).detail || r.statusText);
      const inf = await r.json();
      mensaje(`Informe generado (versión ${inf.version}, tipo ${inf.tipo_informe}).`);
      const urlInforme = `/api/v1/episodios/${episodioId}/informes/${inf.id}/html`;
      $("enlace-informe").href = urlInforme;
      $("enlace-imprimir").href = urlInforme;
      $("enlaces-informe").hidden = false;
      $("btn-finalizar").disabled = false;
    } catch (e) {
      mensaje("Error al generar el informe: " + e.message, true);
    } finally {
      btn.disabled = false;
    }
  }

  async function finalizarAtencion() {
    const btn = $("btn-finalizar");
    btn.disabled = true;
    try {
      const r = await fetch(`/api/v1/episodios/${episodioId}/cerrar`, {
        method: "POST",
      });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      mensaje("Atención finalizada. Gracias por utilizar el tótem.");
      $("btn-generar").disabled = true;
      try {
        sessionStorage.removeItem("episodio_id");
      } catch (_) {}
      setTimeout(() => (window.location.href = "/"), 4000);
    } catch (e) {
      btn.disabled = false;
      mensaje("Error al finalizar: " + e.message, true);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!episodioId) {
      mensaje("No se encontró un episodio activo.", true);
      $("btn-generar").disabled = true;
      return;
    }
    $("btn-generar").addEventListener("click", generarInforme);
    $("btn-finalizar").addEventListener("click", finalizarAtencion);
    cargarTrazabilidad();
    setInterval(cargarTrazabilidad, 5000); // actualización en tiempo real
  });
})();