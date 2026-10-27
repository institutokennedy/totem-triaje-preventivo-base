document.addEventListener('DOMContentLoaded', () => {
    const secInstrucciones = document.getElementById('estado-instrucciones');
    const secMidiendo = document.getElementById('estado-midiendo');
    const secResultado = document.getElementById('estado-resultado');
    const secConfirmado = document.getElementById('estado-confirmado');
    const secError = document.getElementById('estado-error');

    const resValor = document.getElementById('res-valor');
    const resUnidad = document.getElementById('res-unidad');
    const resMetodo = document.getElementById('res-metodo');
    const mensajeError = document.getElementById('mensaje-error');

    const btnComenzar = document.getElementById('btn-comenzar');
    const btnRepetir = document.getElementById('btn-repetir');
    const btnConfirmar = document.getElementById('btn-confirmar');
    const btnReintentar = document.getElementById('btn-reintentar');
    const btnContinuar = document.getElementById('btn-continuar');

    let medicionCapturada = null;

    function mostrarEstado(estadoActivo) {
        [secInstrucciones, secMidiendo, secResultado, secConfirmado, secError].forEach(sec => {
            if (sec) sec.style.display = 'none';
        });
        if (estadoActivo) estadoActivo.style.display = 'block';
    }

    async function obtenerDispositivoId() {
        try {
            const res = await fetch('/api/v1/dispositivos');
            if (!res.ok) throw new Error('Error al consultar dispositivos');
            const dispositivos = await res.json();
            const dispositivoGlu = dispositivos.find(d => d.codigo === 'GLU-001');
            return dispositivoGlu ? dispositivoGlu.id : null;
        } catch (e) {
            console.error('Error al consultar dispositivos:', e);
            return null;
        }
    }

    btnComenzar.addEventListener('click', () => {
        mostrarEstado(secMidiendo);

        setTimeout(() => {
            medicionCapturada = {
                valor: parseFloat((Math.random() * (140 - 80) + 80).toFixed(1)),
                unidad: 'mg/dL',
                metodo: 'FOTODIODO_NO_INVASIVO'
            };

            resValor.textContent = medicionCapturada.valor;
            resUnidad.textContent = medicionCapturada.unidad;
            resMetodo.textContent = medicionCapturada.metodo;

            mostrarEstado(secResultado);
        }, 2000);
    });

    btnRepetir.addEventListener('click', () => {
        medicionCapturada = null;
        mostrarEstado(secInstrucciones);
    });

    if (btnReintentar) {
        btnReintentar.addEventListener('click', () => {
            mostrarEstado(secInstrucciones);
        });
    }

    btnConfirmar.addEventListener('click', async () => {
        if (!medicionCapturada) return;

        const urlParams = new URLSearchParams(window.location.search);
        const episodioId = parseInt(urlParams.get('episodio_id') || localStorage.getItem('episodio_id') || '1');

        const dispositivoId = await obtenerDispositivoId();

        if (!dispositivoId) {
            mensajeError.textContent = 'No se encontró el dispositivo GLU-001 registrado en la base de datos.';
            mostrarEstado(secError);
            return;
        }

        const payload = {
            episodio_id: episodioId,
            dispositivo_id: dispositivoId,
            origen: 'SENSOR',
            data: {
                valor: medicionCapturada.valor,
                unidad: medicionCapturada.unidad,
                metodo: medicionCapturada.metodo
            }
        };

        try {
            const respuesta = await fetch('/api/v1/glucemia/resultados', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (respuesta.status === 201 || respuesta.ok) {
                mostrarEstado(secConfirmado);
            } else {
                const errorData = await respuesta.json().catch(() => ({}));
                mensajeError.textContent = errorData.detail || 'Ocurrió un error al guardar la medición.';
                mostrarEstado(secError);
            }
        } catch (error) {
            mensajeError.textContent = 'Error de red o conexión con la API.';
            mostrarEstado(secError);
        }
    });

    if (btnContinuar) {
        btnContinuar.addEventListener('click', () => {
            window.location.href = '/episodio';
        });
    }
});