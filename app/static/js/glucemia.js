document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const episodioId = parseInt(urlParams.get('episodio_id') || localStorage.getItem('episodio_id') || '1');

    // Elementos del DOM por estado
    const estadoInstrucciones = document.getElementById('estado-instrucciones');
    const estadoMidiendo = document.getElementById('estado-midiendo');
    const estadoResultado = document.getElementById('estado-resultado');
    const estadoError = document.getElementById('estado-error');
    const estadoConfirmado = document.getElementById('estado-confirmado');

    // Botones y controles
    const btnComenzar = document.getElementById('btn-comenzar');
    const btnRepetir = document.getElementById('btn-repetir');
    const btnConfirmar = document.getElementById('btn-confirmar');
    const btnReintentar = document.getElementById('btn-reintentar');
    const btnVolverPanel = document.getElementById('btn-volver-panel');
    const selectOrigen = document.getElementById('select-origen');

    const resValor = document.getElementById('res-valor');
    const resUnidad = document.getElementById('res-unidad');
    const resMetodo = document.getElementById('res-metodo');
    const msgError = document.getElementById('msg-error');

    let lecturaActual = null;
    let dispositivoId = null;

    // Recuperar el dispositivo_id generado por SQLite para "GLU-001"
    async function obtenerDispositivoId() {
        try {
            const res = await fetch('/api/v1/dispositivos');
            if (res.ok) {
                const dispositivos = await res.json();
                const disp = dispositivos.find(d => d.codigo === 'GLU-001');
                if (disp) {
                    dispositivoId = disp.id;
                } else {
                    mostrarError("No se encontró el dispositivo GLU-001 registrado en SQLite.");
                }
            }
        } catch (e) {
            mostrarError("Error al conectar con la API para consultar dispositivos.");
        }
    }

    await obtenerDispositivoId();

    function cambiarEstado(estado) {
        [estadoInstrucciones, estadoMidiendo, estadoResultado, estadoError, estadoConfirmado].forEach(el => {
            if (el) el.style.display = 'none';
        });

        if (estado === 'INSTRUCCIONES') estadoInstrucciones.style.display = 'block';
        if (estado === 'MIDIENDO') estadoMidiendo.style.display = 'block';
        if (estado === 'RESULTADO') estadoResultado.style.display = 'block';
        if (estado === 'ERROR') estadoError.style.display = 'block';
        if (estado === 'CONFIRMADO') estadoConfirmado.style.display = 'block';
    }

    function mostrarError(mensaje) {
        msgError.textContent = mensaje;
        cambiarEstado('ERROR');
    }

    // Evento Comenzar Medición
    btnComenzar.addEventListener('click', async () => {
        if (!dispositivoId) {
            await obtenerDispositivoId();
            if (!dispositivoId) return;
        }

        cambiarEstado('MIDIENDO');
        const origen = selectOrigen.value;

        try {
            if (origen === 'SIMULADOR') {
                setTimeout(() => {
                    const valorSimulado = parseFloat((Math.random() * (140 - 80) + 80).toFixed(1));
                    lecturaActual = {
                        episodio_id: episodioId,
                        dispositivo_id: dispositivoId,
                        origen: "SIMULADOR",
                        data: {
                            valor: valorSimulado,
                            unidad: "mg/dL",
                            metodo: "SIMULADO"
                        }
                    };
                    mostrarResultado(lecturaActual.data);
                }, 1500);
            } else {
                const res = await fetch(`/api/v1/glucemia/resultados/${episodioId}`);
                if (res.ok) {
                    const lista = await res.json();
                    if (lista.length > 0) {
                        const ult = lista[lista.length - 1];
                        lecturaActual = {
                            episodio_id: ult.episodio_id,
                            dispositivo_id: ult.dispositivo_id,
                            origen: "SENSOR",
                            data: ult.data
                        };
                        mostrarResultado(lecturaActual.data);
                    } else {
                        mostrarError("No se encontraron mediciones registradas por la ESP32 para este episodio.");
                    }
                } else {
                    mostrarError("Error al consultar mediciones del sensor.");
                }
            }
        } catch (err) {
            mostrarError("Falla de red durante la medición.");
        }
    });

    function mostrarResultado(data) {
        resValor.textContent = data.valor;
        resUnidad.textContent = data.unidad;
        resMetodo.textContent = `Método: ${data.metodo}`;
        cambiarEstado('RESULTADO');
    }

    // Botón Repetir (Descarte en memoria sin POST)
    btnRepetir.addEventListener('click', () => {
        lecturaActual = null;
        cambiarEstado('INSTRUCCIONES');
    });

    // Botón Confirmar (Ejecuta el POST a la API)
    btnConfirmar.addEventListener('click', async () => {
        if (!lecturaActual) return;

        try {
            const res = await fetch('/api/v1/glucemia/resultados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(lecturaActual)
            });

            if (res.ok) {
                cambiarEstado('CONFIRMADO');
            } else {
                const errData = await res.json();
                mostrarError(`Error al guardar resultado (${res.status}): ${errData.detail || 'Datos inválidos'}`);
            }
        } catch (e) {
            mostrarError("Error de conexión al intentar confirmar el resultado.");
        }
    });

    btnReintentar.addEventListener('click', () => cambiarEstado('INSTRUCCIONES'));
    btnVolverPanel.addEventListener('click', () => {
        window.location.href = `/episodio?episodio_id=${episodioId}`;
    });
});