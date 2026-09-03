# Tótem de triaje preventivo — repositorio base educativo

Repositorio base del proyecto educativo **Tótem de triaje preventivo**, desarrollado con **FastAPI**, **SQLModel** y **SQLite**.

El objetivo de esta base es que los equipos de estudiantes puedan desarrollar módulos independientes dentro de una misma aplicación, respetando una estructura común y el **Contrato API v1** definido para el proyecto.

> **Estado del proyecto:** la infraestructura general ya funciona y permite registrar pacientes, iniciar episodios de atención, consultar dispositivos y guardar resultados de un módulo de demostración. Los módulos clínicos de los seis grupos todavía deben ser desarrollados por los estudiantes.

---

## 1. ¿Qué está programado hasta ahora?

Actualmente el repositorio incluye:

- aplicación FastAPI ejecutable;
- documentación automática mediante Swagger/OpenAPI;
- base de datos SQLite;
- creación automática de tablas al iniciar la aplicación;
- modelo común de `Paciente`;
- modelo común de `EpisodioAtencion`;
- modelo común de `Dispositivo`;
- modelo común de `ResultadoModulo`;
- módulo para registrar y consultar pacientes;
- módulo para iniciar y consultar episodios de atención;
- módulo para consultar dispositivos;
- módulo de demostración `demo_ambiente`;
- servicio común para almacenar resultados de cualquier módulo;
- datos ficticios de demostración;
- pruebas automáticas con Pytest;
- endpoint `/health` para comprobar que la API está funcionando.

El proyecto **todavía no incluye**:

- reglas clínicas definitivas;
- clasificación por semáforo;
- generación del informe final;
- inteligencia artificial;
- frontend definitivo;
- módulos de signos vitales, ECG, glucemia, boca, vista u oído.

Estos componentes se incorporarán progresivamente durante el desarrollo del proyecto.

---

## 2. Idea general del sistema

El flujo básico que ya puede probarse es:

```text
PACIENTE
   ↓
EPISODIO DE ATENCIÓN
   ↓
DISPOSITIVO
   ↓
MEDICIÓN / RESULTADO
   ↓
BASE DE DATOS
```

En términos prácticos:

1. Se registra un paciente.
2. Se inicia un episodio de atención para ese paciente.
3. Se identifica el dispositivo que realizará la medición.
4. El módulo obtiene o simula un dato.
5. El usuario revisa la información obtenida.
6. El resultado se envía a la API.
7. La API guarda el resultado en SQLite.
8. El resultado puede consultarse posteriormente.

El módulo `demo_ambiente` sirve solamente como ejemplo técnico para comprender este recorrido. No corresponde a ninguno de los seis grupos de trabajo.

---

## 3. Los seis módulos que desarrollarán los estudiantes

Cada grupo trabajará sobre una medición diferente:

1. **Signos vitales**
2. **ECG**
3. **Glucemia**
4. **Boca**
5. **Vista**
6. **Oído**

Cada módulo deberá integrarse a la misma aplicación FastAPI y utilizar los modelos y servicios comunes proporcionados por el repositorio.

Los grupos no deben modificar libremente la estructura común del sistema. La integración entre módulos se realiza mediante el contrato de API acordado.

---

## 4. Tecnologías utilizadas

- **Python**
- **FastAPI**
- **SQLModel**
- **SQLite**
- **Pydantic**
- **Uvicorn**
- **Pytest**

La arquitectura elegida es un **monolito modular**: existe una sola aplicación y una sola base de datos, pero cada funcionalidad se organiza en módulos separados.

---

## 5. Requisitos

Se recomienda utilizar:

- Python 3.11 o superior;
- Git;
- Visual Studio Code u otro editor de código;
- una terminal PowerShell, CMD o terminal de Linux.

Para comprobar la versión de Python:

### Windows

```powershell
py --version
```

### Linux

```bash
python3 --version
```

---

## 6. Descargar el proyecto

Clonar el repositorio:

```bash
git clone https://github.com/preyes/totem-triaje-preventivo-base.git
```

Ingresar a la carpeta:

```bash
cd totem-triaje-preventivo-base
```

---

## 7. Crear y activar el entorno virtual

### Windows — PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Windows — CMD

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Cuando el entorno virtual está correctamente activado, normalmente aparece `(.venv)` al comienzo de la terminal.

---

## 8. Instalar las dependencias

Con el entorno virtual activado:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En algunas distribuciones Linux puede utilizarse `python3` en lugar de `python`.

---

## 9. Ejecutar FastAPI

Desde la carpeta raíz del proyecto:

```bash
python -m uvicorn app.main:app --reload
```

Al iniciar, la aplicación crea automáticamente las tablas necesarias en:

```text
data/totem_triaje.db
```

Si aparece un mensaje similar a:

```text
Uvicorn running on http://127.0.0.1:8000
```

la API está funcionando correctamente.

---

## 10. Abrir Swagger

Con FastAPI ejecutándose, abrir:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Estado de la API: <http://127.0.0.1:8000/health>

Swagger permite probar los endpoints sin necesidad de construir todavía un frontend.

---

## 11. Endpoints disponibles

### Sistema

| Método | Endpoint | Función |
|---|---|---|
| GET | `/health` | Comprueba que la aplicación está funcionando. |

### Pacientes

| Método | Endpoint | Función |
|---|---|---|
| POST | `/api/v1/pacientes` | Registrar un paciente. |
| GET | `/api/v1/pacientes` | Listar todos los pacientes. |
| GET | `/api/v1/pacientes/{paciente_id}` | Consultar un paciente por ID. |

### Episodios

| Método | Endpoint | Función |
|---|---|---|
| POST | `/api/v1/episodios` | Iniciar un episodio de atención. |
| GET | `/api/v1/episodios` | Listar todos los episodios. |
| GET | `/api/v1/episodios/{episodio_id}` | Consultar un episodio por ID. |

### Dispositivos

| Método | Endpoint | Función |
|---|---|---|
| GET | `/api/v1/dispositivos` | Listar todos los dispositivos registrados. |
| GET | `/api/v1/dispositivos/{dispositivo_id}` | Consultar un dispositivo por ID. |

### Demo ambiente

| Método | Endpoint | Función |
|---|---|---|
| POST | `/api/v1/demo-ambiente/resultados` | Guardar una medición ambiental ficticia. |
| GET | `/api/v1/demo-ambiente/resultados` | Listar todos los resultados del módulo de demostración. |
| GET | `/api/v1/demo-ambiente/resultados/{episodio_id}` | Consultar resultados de un episodio. |

---

## 12. Primera prueba recomendada en Swagger

Para comprender el funcionamiento del sistema, conviene realizar las pruebas en este orden.

### Paso 1 — Crear un paciente

Abrir:

```text
POST /api/v1/pacientes
```

Ejemplo:

```json
{
  "dni": "40123456",
  "nombre": "Juan",
  "apellido": "Perez",
  "fecha_nacimiento": "2008-05-12",
  "email": "juan@example.com",
  "telefono": "3515555555"
}
```

La API devolverá un `id` para el paciente.

Ejemplo:

```text
id = 1
```

Ese identificador será necesario para crear el episodio.

---

### Paso 2 — Crear un episodio

Abrir:

```text
POST /api/v1/episodios
```

Ejemplo:

```json
{
  "paciente_id": 1,
  "tipo_circuito": "TRIAJE_PREVENTIVO"
}
```

La API devolverá el identificador del episodio.

Ejemplo:

```text
episodio_id = 1
```

---

### Paso 3 — Consultar los dispositivos

Abrir:

```text
GET /api/v1/dispositivos
```

Para que exista un dispositivo de demostración puede utilizarse el script de datos ficticios explicado en la siguiente sección.

---

### Paso 4 — Guardar un resultado de demostración

Abrir:

```text
POST /api/v1/demo-ambiente/resultados
```

Ejemplo:

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

Los campos:

```text
episodio_id
dispositivo_id
origen
```

forman parte de la estructura común del resultado.

El contenido de:

```text
data
```

depende de cada módulo.

Por ejemplo, el módulo de ECG tendrá datos diferentes del módulo de vista, pero ambos deberán respetar la estructura común acordada.

---

### Paso 5 — Consultar resultados

Para ver todos los resultados de demostración:

```text
GET /api/v1/demo-ambiente/resultados
```

Para consultar los resultados de un episodio determinado:

```text
GET /api/v1/demo-ambiente/resultados/{episodio_id}
```

---

## 13. Cargar datos ficticios automáticamente

También puede cargarse un conjunto de datos de prueba ejecutando:

```bash
python -m scripts.cargar_datos_demo
```

El script crea, si todavía no existen:

- un paciente ficticio;
- un episodio de demostración;
- un dispositivo ambiental simulado;
- un resultado ambiental ficticio.

Al finalizar muestra en la terminal los identificadores creados:

```text
Paciente ID
Episodio ID
Dispositivo ID
Resultado de demostración ID
```

Estos valores pueden utilizarse luego para probar Swagger.

---

## 14. ¿Cómo se guardan los resultados?

Todos los módulos utilizarán la tabla común:

```text
ResultadoModulo
```

Esta tabla almacena:

- `episodio_id`;
- `dispositivo_id`;
- nombre del módulo;
- datos específicos de la medición;
- fecha y hora.

Los datos particulares de cada módulo se guardan como JSON.

Esto evita crear una estructura completamente diferente para cada grupo y facilita la integración final.

Ejemplo conceptual:

```text
ResultadoModulo
│
├── episodio_id = 1
├── dispositivo_id = 1
├── modulo = "demo_ambiente"
└── data_json
       ├── temperatura_c
       └── humedad_porcentaje
```

En un módulo diferente, el contenido de `data_json` cambiará.

---

## 15. Estructura principal del proyecto

```text
app/
│
├── main.py
│
├── core/
│   ├── config.py
│   └── database.py
│
├── common/
│   ├── models.py
│   └── resultado_service.py
│
└── modules/
    │
    ├── pacientes/
    │   ├── router.py
    │   └── schemas.py
    │
    ├── episodios/
    │   ├── router.py
    │   └── schemas.py
    │
    ├── dispositivos/
    │   ├── router.py
    │   └── schemas.py
    │
    └── demo_ambiente/
        ├── router.py
        ├── schemas.py
        ├── simulator.py
        └── test_router.py

scripts/
└── cargar_datos_demo.py

tests/

data/
└── totem_triaje.db
```

---

## 16. ¿Para qué sirve cada parte?

### `app/main.py`

Es el punto de entrada de FastAPI. Crea la aplicación e incorpora los diferentes routers.

### `app/core/database.py`

Administra la conexión con SQLite y las sesiones de SQLModel.

### `app/common/models.py`

Contiene los modelos comunes utilizados por todo el sistema:

- `Paciente`;
- `EpisodioAtencion`;
- `Dispositivo`;
- `ResultadoModulo`.

### `app/common/resultado_service.py`

Contiene funciones comunes para guardar y consultar resultados. Los grupos deben reutilizar este servicio en lugar de crear una forma diferente de almacenamiento para cada módulo.

### `router.py`

Define los endpoints que aparecen en Swagger.

### `schemas.py`

Define la forma que deben tener los datos que ingresan y salen de la API.

### `simulator.py`

Genera datos ficticios para probar un módulo sin depender todavía de sensores físicos.

### `test_router.py`

Comprueba automáticamente que los endpoints principales del módulo funcionan correctamente.

---

## 17. Ejecutar las pruebas automáticas

Con el entorno virtual activado:

```bash
python -m pytest -q
```

Las pruebas utilizan una base SQLite temporal y no deberían modificar:

```text
data/totem_triaje.db
```

---

## 18. Flujo de trabajo con Git y GitHub

Los estudiantes no deben trabajar directamente sobre `main`.

Flujo recomendado:

```text
PULL
 ↓
CREAR RAMA
 ↓
PROGRAMAR
 ↓
STATUS
 ↓
ADD
 ↓
COMMIT
 ↓
PUSH
 ↓
PULL REQUEST
 ↓
REVISIÓN DOCENTE
 ↓
MAIN
```

Ejemplo para crear una rama:

```bash
git checkout -b grupo-signos-vitales
```

Antes de comenzar una nueva jornada de trabajo:

```bash
git pull
```

Para revisar archivos modificados:

```bash
git status
```

Para preparar cambios:

```bash
git add .
```

Para crear un commit:

```bash
git commit -m "Avance modulo signos vitales"
```

Para enviar la rama a GitHub:

```bash
git push -u origin grupo-signos-vitales
```

Luego debe crearse un **Pull Request** para que el docente revise los cambios antes de integrarlos a `main`.

---

## 19. Qué deberán completar los grupos

Durante el proyecto los estudiantes deberán avanzar progresivamente sobre:

1. captura o ingreso de los datos de su módulo;
2. validación técnica de los datos;
3. integración con el episodio de atención;
4. almacenamiento del resultado;
5. pruebas mediante Swagger;
6. pruebas automáticas;
7. incorporación posterior de reglas de orientación definidas para el proyecto;
8. clasificación por semáforo cuando corresponda;
9. participación del módulo en el informe final.

Las reglas clínicas y los criterios de clasificación deberán basarse en documentación oficial y ser validados antes de incorporarse al código.

---

## 20. Importante para los estudiantes

El objetivo del repositorio base no es que cada grupo construya un sistema diferente.

Todos los equipos trabajan sobre el mismo sistema y deben respetar una estructura común.

Cada grupo desarrolla solamente su módulo de medición:

```text
Sistema común
│
├── Pacientes
├── Episodios
├── Dispositivos
├── Resultados
│
├── Signos vitales
├── ECG
├── Glucemia
├── Boca
├── Vista
└── Oído
```

La integración final será posible si todos los grupos respetan el contrato de API, los modelos comunes y la organización modular del repositorio.

---

## 21. Límites de esta versión

El sistema se encuentra en etapa de desarrollo educativo.

El módulo `demo_ambiente` utiliza datos ficticios y existe solamente para mostrar cómo recorrer el camino completo desde una entrada de datos hasta su almacenamiento en la base.

Esta versión no realiza diagnósticos médicos ni reemplaza la evaluación de profesionales de la salud.
