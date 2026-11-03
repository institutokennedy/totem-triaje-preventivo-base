
document.addEventListener("DOMContentLoaded", async () => {
    const CODIGO_DISPOSITIVO = "BOCA-001";

    let dispositivoId = null;

    const estado = document.getElementById("estado-dispositivo");

    async function cargarDispositivo() {
        try {
            const respuesta = await fetch("/api/v1/dispositivos");

            if (!respuesta.ok) {
                throw new Error("No se pudieron consultar los dispositivos");
            }

            const dispositivos = await respuesta.json();

            const dispositivo = dispositivos.find(
                (item) => item.codigo === CODIGO_DISPOSITIVO
            );

            if (!dispositivo) {
                throw new Error("No se encontró el dispositivo BOCA-001");
            }

            if (!dispositivo.activo) {
                throw new Error("El dispositivo BOCA-001 está inactivo");
            }

            dispositivoId = dispositivo.id;

            if (estado) {
                estado.textContent = `Dispositivo conectado: ${dispositivo.codigo} (ID: ${dispositivo.id})`;
            }

            console.log("Dispositivo conectado:", dispositivo);

        } catch (error) {
            dispositivoId = null;

            if (estado) {
                estado.textContent = error.message;
            }

            console.error(error);
        }
    }

    await cargarDispositivo();

    // Permite consultar el ID desde otras funciones del módulo.
    window.obtenerDispositivoBocaId = () => dispositivoId;
});
