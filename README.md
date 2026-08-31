# Tótem de triaje preventivo — repositorio base educativo

Base ejecutable para que los equipos desarrollen módulos independientes dentro de una sola aplicación FastAPI y una sola base SQLite. El ejemplo sigue el **Contrato API v1 aprobado**.

Esta versión incluye infraestructura, modelos comunes y un módulo de demostración técnica. **No contiene reglas clínicas, diagnósticos, inteligencia artificial, frontend ni implementaciones de signos vitales, ECG, glucemia, boca, vista u oído.** Todos los datos incluidos son ficticios.

## Requisitos

- Windows 10 u 11.
- Python 3.11 o superior.
- Una terminal PowerShell o Símbolo del sistema.

Para verificar Python en PowerShell:

```powershell
py --version
```

## 1. Crear y activar el entorno virtual en Windows

Abrir PowerShell dentro de la carpeta del repositorio y ejecutar:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, se puede habilitar solo para esa ventana:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

En Símbolo del sistema (CMD), la activación se realiza con:

```bat
.venv\Scripts\activate.bat
```

## 2. Instalar las dependencias

Con el entorno virtual activado:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Ejecutar FastAPI

Desde la carpeta raíz del repositorio:

```powershell
python -m uvicorn app.main:app --reload
```

La aplicación crea automáticamente las tablas en `data/totem_triaje.db` al iniciar.

Opcionalmente, se puede copiar `.env.example` como `.env` y cargar esa configuración con:

```powershell
python -m uvicorn app.main:app --reload --env-file .env
```

## 4. Abrir Swagger/OpenAPI

Con el servidor en ejecución, abrir en el navegador:

- Swagger UI: <http://127.0.0.1:8000/docs>
- Esquema OpenAPI: <http://127.0.0.1:8000/openapi.json>
- Estado de la API: <http://127.0.0.1:8000/health>

## 5. Cargar datos ficticios

En otra terminal, con el mismo entorno activado:

```powershell
python -m scripts.cargar_datos_demo
```

El comando crea, si todavía no existen:

- un paciente llamado `Paciente Ficticio` con DNI `00000000`;
- un episodio de demostración técnica;
- un dispositivo simulado;
- una lectura ambiental ficticia persistida mediante el servicio común.

Después se pueden consultar o crear nuevas lecturas desde Swagger, en la etiqueta `Demostración: ambiente`.

## 6. Ejecutar las pruebas

```powershell
python -m pytest -q
```

Las pruebas usan una base SQLite temporal. No modifican `data/totem_triaje.db`.

## Endpoints incluidos

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Comprueba que la API responde. |
| POST | `/api/v1/demo-ambiente/resultados` | Registra una lectura ambiental ficticia. |
| GET | `/api/v1/demo-ambiente/resultados/{episodio_id}` | Consulta los resultados de un episodio. |

## Estructura explicada

- `app/main.py`: crea la aplicación, configura Swagger e incorpora los routers.
- `app/core/config.py`: concentra el nombre, versión y URL de la base.
- `app/core/database.py`: crea el motor de SQLModel, abre sesiones y genera las tablas.
- `app/common/models.py`: contiene `Paciente`, `EpisodioAtencion`, `Dispositivo` y `ResultadoModulo`.
- `app/common/resultado_service.py`: servicio entregado por el docente para guardar y consultar resultados.
- `app/models.py`: registra los cuatro modelos comunes.
- `app/modules/demo_ambiente/`: módulo sencillo de ejemplo, ajeno a los seis grupos.
  - `router.py`: define las rutas HTTP.
  - `schemas.py`: describe los datos recibidos y las respuestas.
  - `simulator.py`: produce un JSON ambiental ficticio.
  - `test_router.py`: prueba los dos endpoints del módulo.
- `scripts/cargar_datos_demo.py`: carga un conjunto mínimo de demostración.
- `tests/`: comprueba health, OpenAPI, tablas y datos iniciales.

## Idea del monolito modular

Hay un único proceso FastAPI y una única base SQLite. Cada módulo de medición tiene solamente cuatro archivos: `router.py`, `schemas.py`, `simulator.py` y `test_router.py`.

El módulo `demo_ambiente` recibe esta estructura común:

```json
{
  "episodio_id": 1,
  "dispositivo_id": 1,
  "origen": "SIMULADOR",
  "data": {
    "temperatura_c": 24.5,
    "humedad_porcentaje": 45.0
  }
}
```

Los primeros tres campos son comunes. El contenido de `data` pertenece al módulo. Después de que el usuario revise y confirme la captura, el router llama al servicio común, que guarda `data` como JSON dentro de `ResultadoModulo`.

El ejemplo ambiental no crea una tabla propia. Sirve para observar el recorrido más corto posible:

1. El simulador genera datos ficticios.
2. El usuario los revisa y confirma.
3. Swagger envía el JSON al endpoint `POST`.
4. El servicio común guarda el resultado con SQLModel.
5. El endpoint `GET` permite consultarlo por episodio.
6. Pytest comprueba el funcionamiento en una base temporal.

## Límites de esta entrega

Los directorios y endpoints de signos vitales, ECG, glucemia, boca, vista y oído deberán ser creados por los equipos. Cuando se incorporen reglas de orientación o priorización, deberán respetar la documentación oficial, la validación profesional y el control de versiones definidos para el proyecto. Este repositorio no incluye ninguna regla clínica.
