# Plan de entregas parciales — versión actualizada

**Proyecto:** Tótem de triaje preventivo  
**Cantidad de grupos:** 6  
**Modalidad:** desarrollo incremental, investigación clínica paralela, frontend y backend integrados  
**Fecha:** 6 de septiembre de 2026

## 1. Distribución del trabajo

Todos los grupos realizan cuatro tareas propias del módulo: **investigación clínica, backend, frontend y pruebas**. Además, cada grupo tiene una responsabilidad transversal.

| Grupo | Módulo | Responsabilidad transversal | Frontend transversal | Complejidad |
|---:|---|---|---|---|
| 1 | Signos vitales | Identificación y registro del paciente | Inicio, DNI y registro | Baja-media |
| 2 | ECG | Episodios, circuito y estados | Selección de circuito y episodio activo | Media |
| 3 | Glucemia | Consentimiento y control de continuidad del episodio | Consentimiento y habilitación/bloqueo del recorrido | Media |
| 4 | Boca | Frontend base y navegación | Base, menú, panel y estilos comunes | Media-alta |
| 5 | Vista | Motor de reglas + clasificación | Pantalla de clasificación | Alta |
| 6 | Oído | Informe final + integración E2E | Resumen, informe y cierre | Muy alta |

## 2. Punto de partida entregado

El repositorio base ya resuelve FastAPI, SQLModel/SQLite, modelos comunes, creación de tablas, pacientes básicos, episodios básicos, alta y consulta de dispositivos, `ResultadoModulo`, servicio de persistencia, Swagger y `demo_ambiente`.

Por lo tanto, los estudiantes no rehacen infraestructura ya existente: la utilizan como patrón.

### Dispositivos entregados como infraestructura común

El repositorio base incluye `POST /api/v1/dispositivos`, `GET /api/v1/dispositivos` y `GET /api/v1/dispositivos/{dispositivo_id}`. Cada grupo **utiliza** estos endpoints, pero no debe reprogramarlos.

Antes de persistir resultados, cada equipo debe:

1. registrar su dispositivo ficticio con un `codigo` estable;
2. conservar o recuperar el `id` generado por SQLite;
3. utilizar ese valor como `dispositivo_id`;
4. recordar que el ID puede cambiar entre bases de datos y no está asignado de forma fija al número de grupo.

Códigos sugeridos: `SV-001`, `ECG-001`, `GLU-001`, `BOCA-001`, `VISTA-001` y `OIDO-001`.

## 3. Trabajo clínico en paralelo

Cada grupo investiga exclusivamente su módulo. En cada entrega debe actualizar `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

```text
DESARROLLO TÉCNICO                 INVESTIGACIÓN CLÍNICA
        │                                  │
        ├─ schema                          ├─ fuente oficial
        ├─ simulador                       ├─ página/apartado
        ├─ API                             ├─ población
        ├─ persistencia                    ├─ unidad
        ├─ frontend                        ├─ regla/criterio
        └─ tests                           └─ estado de aprobación
                └──────────────┬──────────────┘
                               ↓
                         INTEGRACIÓN
```

## 4. Entrega 1 — Comprender la base, analizar el módulo y comenzar investigación clínica

### Entregables comunes

- repositorio clonado y ejecutable;
- entorno virtual funcionando;
- Swagger probado;
- prueba de creación de paciente, episodio, dispositivo y demo ambiente;
- ficha del módulo revisada;
- lista inicial de campos, tipos y unidades;
- primer listado de fuentes oficiales encontradas;
- boceto de pantalla del módulo;
- boceto de la pantalla transversal asignada.

### Evidencia

Cada integrante debe poder explicar el recorrido `Paciente → Episodio → ResultadoModulo` y diferenciar validación técnica de decisión clínica.

## 5. Entrega 2 — Schema, simulador, investigación clínica y maqueta frontend

### Backend del módulo

- `schemas.py`;
- `simulator.py`;
- datos ficticios válidos y al menos un error técnico;
- validaciones técnicas mínimas.

### Frontend

- plantilla HTML del módulo sin conexión todavía o con datos simulados;
- estados `INSTRUCCIONES`, `MIDIENDO`, `RESULTADO`, `ERROR`, `CONFIRMADO` representados;
- botones **Comenzar**, **Confirmar** y **Repetir**.

### Investigación clínica

- al menos una fuente oficial pertinente o registro explícito de ausencia de fuente suficiente;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` parcialmente completa;
- dudas clínicas marcadas para revisión.

## 6. Entrega 3 — API, persistencia y frontend conectado

### Backend

- `POST /api/v1/<modulo>/resultados`;
- `GET /api/v1/<modulo>/resultados/{episodio_id}`;
- uso de `resultado_service.py`;
- persistencia en `ResultadoModulo`.

### Frontend

- `fetch()` desde la pantalla del módulo;
- Confirmar realiza el `POST`;
- Repetir no guarda;
- manejo visible de errores de API.

### Tarea transversal

Cada grupo inicia la parte backend/frontend de su responsabilidad transversal.

## 7. Entrega 4 — Responsabilidad transversal funcional

| Grupo | Resultado esperado |
|---:|---|
| 1 | búsqueda por DNI y pantalla de identificación/registro |
| 2 | validación de circuito, estados y pantalla de episodio activo |
| 3 | consentimiento persistido, bloqueo/habilitación del recorrido y su pantalla |
| 4 | `base.html`, navegación, estilos comunes y panel del episodio |
| 5 | motor con reglas de prueba no clínicas, estructura de clasificación y pantalla |
| 6 | estructura de informe, resumen final e inicio de integración E2E |

La tarea transversal debe incluir pruebas propias y documentación de contrato.

## 8. Entrega 5 — Pruebas, reglas aprobadas y robustez

### Pytest

Cada grupo entrega pruebas de:

- caso válido;
- campo faltante;
- tipo incorrecto;
- episodio inexistente;
- persistencia;
- consulta;
- flujo frontend principal;
- componente transversal.

### Investigación clínica

- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` completa para cada regla candidata;
- diferencias entre fuentes documentadas;
- reglas no aprobadas permanecen inactivas;
- solo reglas aprobadas pueden reemplazar reglas ficticias de prueba.

## 9. Entrega 6 — Integración entre grupos

### Objetivo

Probar que cada módulo puede ejecutarse desde el frontend común y guardar resultados en el mismo episodio.

### Entregables

- pantalla del módulo integrada con `base.html`;
- navegación desde el panel del episodio;
- evidencia de un resultado guardado y luego consultado;
- revisión cruzada de otro grupo;
- lista de incidencias de integración.

El grupo revisor no corrige directamente el código ajeno.

## 10. Entrega 7 — Integración final E2E

### Recorrido obligatorio

1. identificar o registrar paciente ficticio;
2. seleccionar circuito;
3. crear episodio;
4. registrar consentimiento;
5. ejecutar los módulos correspondientes;
6. confirmar y guardar resultados;
7. ejecutar reglas aprobadas o reglas de prueba no clínicas;
8. almacenar clasificación cuando corresponda;
9. generar informe preventivo;
10. visualizar resumen final;
11. cerrar el episodio.

### Entregables

- aplicación única ejecutable;
- frontend común navegable;
- Swagger con endpoints;
- SQLite única;
- Pytest sin errores relevantes;
- prueba E2E documentada;
- informe preventivo ficticio;
- registro de incidencias y responsable de cada corrección;
- exposición técnica de cada grupo.

El Grupo 6 coordina la prueba E2E, pero cada grupo corrige los defectos de su propio módulo.

## 11. Control clínico durante todas las entregas

| Situación | Acción obligatoria |
|---|---|
| No existe fuente oficial suficiente | `PENDIENTE DE DEFINICIÓN Y VALIDACIÓN CLÍNICA` |
| Existe fuente pero falta aprobación | mantener regla inactiva |
| Fuentes oficiales difieren | documentar y elevar al profesional responsable |
| Regla ficticia | `REGLAS_DE_PRUEBA_NO_CLINICAS` |
| Regla aprobada | registrar fuente, versión, profesional y pruebas |

## 12. Revisión cruzada

| Revisa | Revisa a |
|---:|---:|
| 1 | 2 |
| 2 | 3 |
| 3 | 4 |
| 4 | 5 |
| 5 | 6 |
| 6 | 1 |

La revisión contempla backend, frontend, contrato JSON, fuentes clínicas, pruebas y documentación.
