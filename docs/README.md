# Kit docente y técnico — versión actualizada

## Archivos principales

- `CONTRATO_API_V1.md`: contrato API/frontend v1.2.
- `PLAN_ENTREGAS_PARCIALES.md`: siete entregas incrementales.
- `FRONTEND_BASE_Y_FLUJO.md`: arquitectura y flujograma del frontend.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`: plantilla única para investigación, trazabilidad, revisión profesional y activación de reglas clínicas.
- `fichas_grupos/`: ficha detallada para cada equipo.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`: guía funcional con anexo de actualización de implementación.

## Distribución transversal

| Grupo | Tarea transversal |
|---:|---|
| 1 | Identificación y registro del paciente |
| 2 | Episodios, circuito y estados |
| 3 | Consentimiento y control de continuidad del episodio |
| 4 | Frontend base y navegación |
| 5 | Motor de reglas y clasificación |
| 6 | Informe final e integración E2E |

## Infraestructura de dispositivos

El alta y consulta de dispositivos quedan resueltas en el repositorio base mediante `POST /api/v1/dispositivos` y los dos `GET` existentes. Ningún grupo programa esa parte. Cada equipo registra un dispositivo ficticio y utiliza el `id` generado por SQLite; el `id` no es fijo por grupo y se recupera a partir del `codigo` del dispositivo.

## Regla común de trabajo

Todos los grupos desarrollan su propia investigación clínica, backend, frontend y pruebas. Las reglas clínicas solo pueden proceder de OMS, Ministerio de Salud de la Nación o Ministerio de Salud de la Provincia de Córdoba y requieren aprobación profesional antes de habilitarse.

## Orden recomendado

1. Leer el contrato.
2. Leer la ficha del grupo.
3. Revisar `demo_ambiente`.
4. Revisar el flujograma frontend.
5. Seguir el plan de entregas.
6. Trabajar la investigación clínica en paralelo.
7. Integrar mediante Pull Request y revisión docente.
