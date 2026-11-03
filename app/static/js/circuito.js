(() => {
  "use strict";

  async function json(url, options) {
    const response = await fetch(url, options);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body.detail === "string" ? body.detail : "HTTP " + response.status;
      throw new Error(detail + " (" + response.status + ").");
    }
    return body;
  }

  const app = document.getElementById("circuito-app");
  if (!app) return;
  const message = app.querySelector("#mensaje");
  const radios = [...app.querySelectorAll('input[name="tipo_circuito"]')];
  const activeEpisode = app.querySelector("#episodio-activo");
  const openEcg = app.querySelector("#abrir-ecg");

  function formatEpisodeDate(value) {
    if (typeof value !== "string") return "No informada por la API.";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "No informada por la API.";
    return new Intl.DateTimeFormat("es-AR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(date);
  }

  async function loadActiveEpisode() {
    const rawId = new URLSearchParams(window.location.search).get("episodio_id");
    if (rawId === null) return;
    if (!/^[1-9]\d*$/.test(rawId) || !Number.isSafeInteger(Number(rawId))) {
      message.textContent = "El episodio_id recibido no es válido. No se habilitó la navegación al ECG.";
      message.setAttribute("role", "alert");
      return;
    }

    const episodeId = Number(rawId);
    message.textContent = `Consultando el episodio activo #${episodeId}…`;
    try {
      const episode = await json(`/api/v1/episodios/${episodeId}`, {
        headers: { Accept: "application/json" },
      });
      if (episode.id !== episodeId || !Number.isSafeInteger(episode.paciente_id) || episode.paciente_id <= 0 ||
          !["GUARDIA", "COMPLETO"].includes(episode.tipo_circuito)) {
        throw new Error("La API no devolvió un episodio compatible con el contrato.");
      }
      app.querySelector("#episodio-id").textContent = String(episode.id);
      app.querySelector("#paciente-id").textContent = String(episode.paciente_id);
      app.querySelector("#episodio-circuito").textContent = episode.tipo_circuito;
      app.querySelector("#episodio-inicio").textContent = formatEpisodeDate(episode.iniciado_en);
      app.querySelector("#episodio-estado").textContent = episode.estado;
      activeEpisode.hidden = false;
      openEcg.href = `/api/v1/ecg/pantalla?episodio_id=${encodeURIComponent(episode.id)}`;
      openEcg.hidden = false;
      message.textContent = `Episodio #${episode.id} consultado. El enlace al ECG conserva el ID devuelto por la API.`;
      message.setAttribute("role", "status");
    } catch (error) {
      message.textContent = error instanceof Error ? error.message : "No se pudo consultar el episodio activo.";
      message.setAttribute("role", "alert");
    }
  }

  for (const radio of radios) {
    radio.addEventListener("change", () => {
      if (radio.checked) {
        message.textContent = "Circuito " + radio.value + " seleccionado. La creación espera el paciente real del flujo de identificación.";
        message.setAttribute("role", "status");
      }
    });
  }
  void loadActiveEpisode();

})();
