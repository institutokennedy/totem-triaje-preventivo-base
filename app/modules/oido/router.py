import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.models import Dispositivo, EpisodioAtencion, ResultadoModulo
from app.modules.oido.schemas import ResultadoOidoCreate

router = APIRouter(prefix="/api/v1/oido", tags=["oido"])
pages_router = APIRouter(tags=["oido-paginas"])

MODULO = "oido"


@pages_router.get("/oido", include_in_schema=False)
def pagina_oido(episodio_id: int | None = None):
    episodio = episodio_id if episodio_id is not None else ""
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Evaluación auditiva</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f7fb; color: #1f2937; }}
                .card {{ max-width: 760px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.08); }}
                h1, h2 {{ margin-top: 0; }}
                button {{ background: #1d4ed8; color: white; border: none; border-radius: 8px; padding: 0.8rem 1.2rem; font-size: 1rem; cursor: pointer; margin-right: 0.75rem; }}
                button.secondary {{ background: #475569; }}
                .row {{ display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem; }}
                .hidden {{ display: none; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
                th, td {{ border: 1px solid #d1d5db; padding: 0.6rem; text-align: left; }}
                .status {{ margin-top: 1rem; color: #0f766e; font-weight: 600; }}
                .status.error {{ color: #b91c1c; }}
            </style>
        </head>
        <body>
            <div class="card">
                <section id="inicio">
                    <h1>Evaluación auditiva</h1>
                    <p>Paciente con episodio {episodio}</p>
                    <div class="row">
                        <button id="btn-comenzar" type="button">Comenzar medición</button>
                    </div>
                </section>

                <section id="medicion" class="hidden">
                    <h2>Medición</h2>
                    <p>Oído: <strong id="oido-actual">derecho</strong></p>
                    <p>Frecuencia: <strong id="frecuencia-actual">500</strong> Hz</p>
                    <div class="row">
                        <button id="btn-escuche">Escuché</button>
                        <button id="btn-no-escuche" class="secondary">No escuché</button>
                    </div>
                </section>

                <section id="resumen" class="hidden">
                    <h2>Resumen</h2>
                    <table>
                        <thead>
                            <tr><th>Frecuencia (Hz)</th><th>Oído derecho</th><th>Oído izquierdo</th></tr>
                        </thead>
                        <tbody id="tabla-body"></tbody>
                    </table>
                    <div class="row">
                        <button id="btn-confirmar">Confirmar</button>
                        <button id="btn-repetir" class="secondary">Repetir</button>
                    </div>
                </section>

                <p id="estado" class="status" aria-live="polite"></p>
            </div>

            <script>
                const frecuencias = [500, 1000, 2000, 4000];
                const oidos = ['derecho', 'izquierdo'];
                const estado = {{
                    episodioId: Number(new URLSearchParams(window.location.search).get('episodio_id') || '{episodio}'),
                    dispositivoId: 1,
                    indice: 0,
                    oidoIdx: 0,
                    derecho: [],
                    izquierdo: []
                }};

                function mostrarSeccion(id) {{
                    document.getElementById('inicio').classList.toggle('hidden', id !== 'inicio');
                    document.getElementById('medicion').classList.toggle('hidden', id !== 'medicion');
                    document.getElementById('resumen').classList.toggle('hidden', id !== 'resumen');
                }}

                function actualizarEstimulacion() {{
                    document.getElementById('oido-actual').textContent = oidos[estado.oidoIdx];
                    document.getElementById('frecuencia-actual').textContent = frecuencias[estado.indice];
                }}

                function mensaje(texto, error = false) {{
                    const el = document.getElementById('estado');
                    el.textContent = texto;
                    el.classList.toggle('error', error);
                }}

                function registrarRespuesta(escucho) {{
                    const lista = estado.oidoIdx === 0 ? estado.derecho : estado.izquierdo;
                    lista.push(escucho);
                    estado.indice += 1;
                    if (estado.indice >= frecuencias.length) {{
                        estado.indice = 0;
                        estado.oidoIdx += 1;
                    }}
                    if (estado.oidoIdx >= oidos.length) {{
                        const tbody = document.getElementById('tabla-body');
                        tbody.innerHTML = '';
                        frecuencias.forEach((f, i) => {{
                            const tr = document.createElement('tr');
                            tr.innerHTML = `<td>${{f}}</td><td>${{estado.derecho[i] ? 'Respuesta registrada' : 'Sin respuesta'}}</td><td>${{estado.izquierdo[i] ? 'Respuesta registrada' : 'Sin respuesta'}}</td>`;
                            tbody.appendChild(tr);
                        }});
                        mostrarSeccion('resumen');
                        return;
                    }}
                    actualizarEstimulacion();
                }}

                function confirmar() {{
                    const payload = {{
                        episodio_id: estado.episodioId,
                        dispositivo_id: estado.dispositivoId,
                        origen: 'SIMULADOR',
                        data: {{
                            frecuencias_hz: frecuencias,
                            resultados_oido_derecho: estado.derecho,
                            resultados_oido_izquierdo: estado.izquierdo,
                        }}
                    }};
                    fetch('/api/v1/oido/resultados', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(payload)
                    }}).then(async (response) => {{
                        if (!response.ok) {{
                            throw new Error('No se pudo guardar el resultado');
                        }}
                        mensaje('Resultado guardado correctamente.');
                        const url = '/resumen' + (estado.episodioId ? '?episodio_id=' + estado.episodioId : '');
                        window.location.href = url;
                    }}).catch((error) => {{
                        mensaje(error.message, true);
                    }});
                }}

                document.getElementById('btn-comenzar').addEventListener('click', () => {{
                    estado.derecho = [];
                    estado.izquierdo = [];
                    estado.indice = 0;
                    estado.oidoIdx = 0;
                    mostrarSeccion('medicion');
                    actualizarEstimulacion();
                }});

                document.getElementById('btn-escuche').addEventListener('click', () => registrarRespuesta(true));
                document.getElementById('btn-no-escuche').addEventListener('click', () => registrarRespuesta(false));
                document.getElementById('btn-confirmar').addEventListener('click', confirmar);
                document.getElementById('btn-repetir').addEventListener('click', () => {{
                    mostrarSeccion('inicio');
                    mensaje('');
                }});
            </script>
        </body>
        </html>
        """
    )


@pages_router.get("/resumen", include_in_schema=False)
def pagina_resumen(episodio_id: int | None = None):
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="es">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Resumen del episodio</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f7fb; color: #1f2937; }}
                .card {{ max-width: 760px; margin: 0 auto; background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.08); }}
                h1 {{ margin-top: 0; }}
                button {{ background: #0f766e; color: white; border: none; border-radius: 8px; padding: 0.8rem 1.2rem; font-size: 1rem; cursor: pointer; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Resumen del episodio</h1>
                <p>Se registró el episodio con identificador: <strong>{episodio_id if episodio_id is not None else 'sin dato'}</strong></p>
                <p>El resultado del módulo de oído ya fue enviado a la API.</p>
                <button type="button" onclick="window.location.href='/oido'">Volver al módulo</button>
            </div>
        </body>
        </html>
        """
    )


MODULO = "oido"


def _serializar(registro: ResultadoModulo) -> dict:
    salida = registro.model_dump()
    try:
        salida["data_json"] = json.loads(registro.data_json)
    except (TypeError, ValueError):
        pass
    return salida


@router.post("/resultados", status_code=status.HTTP_201_CREATED)
def crear_resultado_oido(payload: ResultadoOidoCreate, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, payload.episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    if session.get(Dispositivo, payload.dispositivo_id) is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    registro = ResultadoModulo(
        episodio_id=payload.episodio_id,
        dispositivo_id=payload.dispositivo_id,
        modulo=MODULO,
        origen=payload.origen,
        data_json=json.dumps(payload.data.model_dump()),
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return _serializar(registro)


@router.get("/resultados/{episodio_id}", response_model=List[dict])
def listar_resultados_oido(episodio_id: int, session: Session = Depends(get_session)):
    if session.get(EpisodioAtencion, episodio_id) is None:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    registros = session.exec(
        select(ResultadoModulo).where(
            ResultadoModulo.episodio_id == episodio_id,
            ResultadoModulo.modulo == MODULO,
        )
    ).all()
    return [_serializar(r) for r in registros]
