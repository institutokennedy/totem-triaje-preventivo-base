(() => {
  "use strict";

  const boton = document.getElementById("btn-comenzar");
  const mensaje = document.getElementById("inicio-mensaje");

  function mostrarMensaje(texto) {
    mensaje.textContent = texto;
  }

  async function iniciarEpisodio() {
    const respuesta = await fetch("/api/v1/episodios/audiometria", {
      method: "POST",
    });
    const episodio = await respuesta.json();
    if (!respuesta.ok) {
      throw new Error(
        typeof episodio.detail === "string"
          ? episodio.detail
          : "No se pudo iniciar una nueva prueba de audiometría."
      );
    }
    if (!Number.isInteger(episodio.id) || episodio.id <= 0) {
      throw new Error("El servidor no devolvió un episodio válido.");
    }
    return episodio.id;
  }

  function abrirEpisodio(episodioId) {
    sessionStorage.setItem("episodio_id", String(episodioId));
    window.location.assign(`/oido?episodio_id=${encodeURIComponent(episodioId)}`);
  }

  boton.addEventListener("click", async () => {
    boton.disabled = true;
    mostrarMensaje("");

    try {
      const episodioId = await iniciarEpisodio();
      abrirEpisodio(episodioId);
    } catch (error) {
      mostrarMensaje(error.message);
    } finally {
      boton.disabled = false;
    }
  });
})();
