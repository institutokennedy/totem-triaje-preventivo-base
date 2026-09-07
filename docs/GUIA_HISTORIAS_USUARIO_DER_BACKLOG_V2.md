# Guía de historias de usuario, DER y backlog — v2

Este archivo identifica la guía funcional general del proyecto y deja asentada la actualización de implementación vigente para el trabajo de los estudiantes.

## Alcance de la guía funcional

La guía general organiza el proyecto desde el análisis funcional hasta la programación: circuito de guardia, circuito completo, historias de usuario HU-01 a HU-20, reglas de negocio, entidades conceptuales, DER, relación entre historias y datos, backlog e integración.

El DER conceptual de esa guía representa una visión funcional amplia. Para la implementación educativa actual no se exige crear desde el inicio todas sus entidades.

## Implementación vigente

Para el desarrollo actual prevalecen, en este orden:

1. `CONTRATO_API_V1.md`.
2. La ficha específica de cada grupo en `fichas_grupos/`.
3. `PLAN_ENTREGAS_PARCIALES.md`.
4. `FRONTEND_BASE_Y_FLUJO.md`.
5. `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
6. Esta guía como marco funcional general.

La persistencia común entregada parte de cuatro modelos: `Paciente`, `EpisodioAtencion`, `Dispositivo` y `ResultadoModulo`. Los modelos auxiliares de consentimiento, clasificación e informe se incorporan únicamente dentro de las tareas transversales correspondientes y con revisión docente.

## Distribución transversal actualizada

| Grupo | Módulo | Responsabilidad transversal |
|---:|---|---|
| 1 | Signos vitales | Identificación y registro del paciente |
| 2 | ECG | Episodios, selección de circuito y estados |
| 3 | Glucemia | Consentimiento y control de continuidad del episodio |
| 4 | Boca | Frontend base y navegación común |
| 5 | Vista | Motor de reglas y clasificación por semáforo |
| 6 | Oído | Informe final e integración E2E |

## Frontend

El frontend forma parte del trabajo estudiantil. Se implementa en la misma aplicación FastAPI mediante Jinja2, HTML, CSS y JavaScript básico. Cada grupo desarrolla la pantalla de su módulo y la responsabilidad transversal indicada en su ficha.

El recorrido general es:

```text
Identificación del paciente
        ↓
Selección de circuito
        ↓
Creación del episodio
        ↓
Consentimiento
        ↓
Panel del episodio
        ↓
Módulos de medición
        ↓
Clasificación cuando corresponda
        ↓
Informe preventivo
        ↓
Resumen y cierre
```

## Dispositivos

El alta y consulta de dispositivos son infraestructura común ya entregada. Los grupos utilizan:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

El `dispositivo_id` no es fijo por grupo. SQLite lo genera al registrar el dispositivo y cada equipo lo recupera a partir de un `codigo` estable.

## Reglas clínicas

Cada grupo investiga las especificaciones clínicas de su propio módulo. La trazabilidad, fuentes, diferencias entre documentos, revisión profesional, versión y estado de activación se registran únicamente mediante `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

No se habilita ninguna regla clínica sin fuente oficial admitida, trazabilidad completa y aprobación profesional. Las reglas de desarrollo deben quedar identificadas como `REGLAS_DE_PRUEBA_NO_CLINICAS`.

## Nota sobre la versión visual

La versión DOCX completa de la guía conserva el desarrollo extenso del DER, las fichas de historias de usuario y las figuras didácticas. Este archivo Markdown funciona como referencia de implementación dentro del repositorio y evita duplicar información que ya está detallada en el contrato, las fichas y el plan de entregas.
