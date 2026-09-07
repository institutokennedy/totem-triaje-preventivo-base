# Ficha del Grupo 6 — Oído

**Módulo de medición:** evaluación auditiva básica  
**Responsabilidad transversal:** informe final e integración E2E  
**Frontend transversal:** resumen final, informe y cierre del episodio  
**Historias relacionadas:** HU-15, HU-19, HU-20 y requisitos transversales de integración

## 0. Documentos que el grupo debe consultar

- `CONTRATO_API_V1.md`.
- `PLAN_ENTREGAS_PARCIALES.md`.
- `FRONTEND_BASE_Y_FLUJO.md`.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`.

## 1. Objetivo del grupo

Desarrollar un módulo que registre respuestas ficticias para distintas frecuencias y ambos oídos. Además, asumir la responsabilidad transversal de mayor integración: construir el informe preventivo final y coordinar pruebas E2E del recorrido completo.

El módulo no determina pérdida auditiva ni produce diagnósticos.

## 2. Punto de partida del repositorio

Ya existen pacientes, episodios, dispositivos, resultados comunes y el módulo de demostración. Los demás módulos y responsabilidades transversales se integrarán progresivamente.

El Grupo 6 **coordina y prueba** la integración, pero no corrige directamente el código de otros grupos sin acuerdo/Pull Request.

La infraestructura común también incluye el alta y consulta de dispositivos mediante API. Cada grupo la utiliza para obtener el `dispositivo_id` de sus pruebas, pero no la reimplementa.

## 3. Recorrido del usuario del módulo

### Antes de la prueba

1. Mostrar instrucciones sencillas.
2. Verificar auriculares, dispositivo o simulador.
3. Esperar que el usuario presione **Comenzar**.

### Durante la prueba

1. Indicar el oído evaluado.
2. Presentar estímulos ficticios.
3. Registrar respuestas verdaderas o falsas.
4. Informar una interrupción y permitir repetir.

### Después de la prueba

1. Mostrar un resumen técnico.
2. Permitir **Confirmar** o **Repetir**.
3. Guardar después de confirmar.
4. Permitir continuar al paso siguiente del circuito.

## 4. Responsabilidades del módulo

- Crear schemas y simulador.
- Implementar endpoints `POST` y `GET`.
- Validar listas y correspondencia de posiciones.
- Guardar en `ResultadoModulo`.
- Construir pantalla Oído.
- Escribir pruebas automáticas.
- Documentar investigación clínica propia en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `dispositivo_id` | `int` | Sí |
| `origen` | `str` | Sí |
| `data` | `DatosOido` | Sí |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `OIDO-001`
- `tipo`: `OIDO`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 6** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad | Obligatorio |
|---|---|---|---:|
| `frecuencias_hz` | `list[int]` | Hz | Sí |
| `resultados_oido_derecho` | `list[bool]` | respuesta sí/no | Sí |
| `resultados_oido_izquierdo` | `list[bool]` | respuesta sí/no | Sí |

Las tres listas deben tener la misma cantidad de elementos. Cada posición corresponde a la misma frecuencia.

## 7. Validaciones técnicas mínimas

- listas con al menos un elemento;
- misma longitud en las tres listas;
- frecuencias enteras mayores que cero;
- respuestas `true` o `false`;
- IDs positivos;
- episodio y dispositivo existentes;
- no interpretar clínicamente el patrón de respuestas.

## 8. Endpoints del módulo

```text
POST /api/v1/oido/resultados
GET  /api/v1/oido/resultados/{episodio_id}
```

## 9. Estructura recomendada

```text
app/modules/oido/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

El resultado utiliza `modulo = "oido"`. Las tres listas se serializan dentro de `data_json` y se recuperan con el mismo formato.

## 11. Frontend propio del módulo

Consultar `FRONTEND_BASE_Y_FLUJO.md`. La pantalla Oído debe:

- mostrar instrucciones;
- indicar oído/frecuencia en prueba cuando corresponda;
- mostrar un resumen técnico sin interpretación;
- permitir repetir;
- confirmar antes del `POST`;
- continuar al panel/resumen.

Archivos sugeridos:

```text
app/templates/modulos/oido.html
app/static/js/oido.js
```

## 12. Investigación clínica propia del grupo

El Grupo 6 investiga exclusivamente las especificaciones de evaluación auditiva que correspondan al proyecto: procedimiento, frecuencias, lateralidad, condiciones, población y criterios candidatos.

Toda evidencia clínica se documenta en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. El trabajo de informe e integración no autoriza al grupo a modificar reglas clínicas de otros equipos.

## 13. Tarea transversal A — Informe final

### Objetivo

Generar un informe preventivo del episodio a partir de información persistida, sin inventar datos ni realizar diagnósticos.

### Endpoints a desarrollar

```text
POST /api/v1/episodios/{episodio_id}/informes
GET  /api/v1/episodios/{episodio_id}/informes
```

### Datos que debe recuperar

- paciente asociado al episodio;
- datos básicos del episodio;
- `ResultadoModulo` disponibles;
- clasificación, si existe y es válida;
- módulos faltantes o con error;
- fecha/hora de generación.

### Contenido mínimo

- identificación ficticia del paciente;
- episodio y circuito;
- resultados disponibles organizados por módulo;
- módulos faltantes/incompletos;
- clasificación preventiva cuando corresponda;
- versión/regla referenciada cuando el contrato lo requiera;
- advertencia: **“Informe preventivo. No constituye un diagnóstico médico.”**

### Persistencia

El grupo puede crear un modelo auxiliar de informe con revisión docente. Debe conservar como mínimo:

- episodio;
- tipo/versión de informe;
- ruta o referencia del archivo/contenido;
- fecha/hora;
- estado.

No se sobrescriben informes históricos si luego se genera una nueva versión.

### Frontend de informe/resumen

Debe mostrar:

- módulos realizados y pendientes;
- estado del episodio;
- clasificación si corresponde;
- botón para generar/ver informe;
- errores de generación;
- opción de finalizar el recorrido cuando el flujo lo permita.

## 14. Tarea transversal B — Integración E2E

### Objetivo

Comprobar que las piezas de los seis grupos funcionan como una sola aplicación.

### Recorrido mínimo de prueba

```text
Identificar/registrar paciente
        ↓
Seleccionar circuito
        ↓
Crear episodio
        ↓
Registrar consentimiento
        ↓
Ejecutar módulos correspondientes
        ↓
Confirmar y guardar resultados
        ↓
Procesar/clasificar cuando corresponda
        ↓
Generar informe
        ↓
Mostrar resumen y finalizar
```

### Responsabilidades del Grupo 6 en E2E

- preparar datos ficticios de integración;
- ejecutar el recorrido completo;
- comprobar que se conserva el mismo `episodio_id`;
- verificar que cada resultado queda asociado al episodio;
- comprobar navegación entre pantallas;
- comprobar clasificación/informe cuando estén disponibles;
- registrar incidencias con módulo, endpoint/pantalla, esperado y obtenido;
- devolver cada incidencia al grupo responsable;
- volver a ejecutar la prueba después de las correcciones.

### El Grupo 6 no debe

- cambiar unilateralmente schemas de otros grupos;
- corregir directamente código ajeno sin coordinación;
- alterar una regla clínica para hacer pasar una prueba;
- reemplazar datos faltantes por valores inventados.

## 15. Pruebas mínimas del grupo

1. Resultado auditivo válido.
2. Listas vacías.
3. Listas con distinta cantidad de elementos.
4. Frecuencia enviada como texto.
5. Falta de una lista.
6. Episodio inexistente.
7. Persistencia y consulta.
8. **Repetir/Confirmar**.
9. Informe con todos los resultados disponibles.
10. Informe con módulos faltantes.
11. Informe construido desde SQLite.
12. Nueva versión de informe sin destruir la anterior.
13. Recorrido E2E con varios módulos.
14. Error de integración registrado y asignado al grupo responsable.
15. Cierre/resumen final visible.

## 16. Criterios de aceptación

- Endpoints Oído visibles en Swagger.
- Listas validadas correctamente.
- Resultado asociado al episodio.
- Pantalla Oído integrada.
- Informe recupera datos persistidos.
- Informe identifica faltantes y contiene advertencia preventiva.
- Historial de informes no se pierde.
- Prueba E2E documentada.
- Incidencias de otros grupos se documentan, no se ocultan.
- Todas las pruebas propias pasan.
- No se interpreta clínicamente la prueba auditiva.

## 17. Entregables específicos

- backend/frontend Oído;
- generador y endpoints de informes;
- persistencia auxiliar de informes;
- resumen final y pantalla de informe;
- casos/datos E2E;
- informe de incidencias de integración;
- evidencias Swagger/Pytest;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` del módulo Oído.

## 18. No debe modificar

- configuración y modelos comunes sin autorización;
- contratos de otros módulos;
- fuentes o reglas clínicas de otros grupos;
- resultados históricos;
- clasificaciones históricas;
- frontend base del Grupo 4 sin coordinación.

## 19. Estado clínico durante el desarrollo

Las frecuencias y respuestas de simulación son ficticias. La investigación y aprobación clínica del módulo se gestiona únicamente mediante `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
