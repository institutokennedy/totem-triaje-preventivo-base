# Ficha del Grupo 5 — Vista

**Módulo de medición:** evaluación visual básica  
**Responsabilidad transversal:** motor de reglas y clasificación por semáforo  
**Frontend transversal:** pantalla de procesamiento/clasificación  
**Historias relacionadas:** HU-06, HU-17 y HU-18

## 0. Documentos que el grupo debe consultar

- `CONTRATO_API_V1.md`.
- `PLAN_ENTREGAS_PARCIALES.md`.
- `FRONTEND_BASE_Y_FLUJO.md`.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`.

## 1. Objetivo del grupo

Desarrollar un módulo que registre resultados ficticios para ojo derecho e izquierdo y asumir una de las responsabilidades de mayor complejidad: construir un motor que ejecute reglas autorizadas sobre resultados persistidos y genere una clasificación preventiva trazable.

El módulo Vista no interpreta por sí mismo la capacidad visual. La clasificación general es priorización/orientación preventiva y no un diagnóstico.

## 2. Punto de partida del repositorio

Ya existe la persistencia común en `ResultadoModulo`. Aún deben desarrollarse el motor de reglas y los endpoints de clasificación.

Cada grupo investiga las reglas de **su propio módulo**. El Grupo 5 no decide ni completa reglas clínicas de otros grupos: su motor recibe reglas ya documentadas y con el estado correspondiente en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

La infraestructura común también incluye el alta y consulta de dispositivos mediante API. Cada grupo la utiliza para obtener el `dispositivo_id` de sus pruebas, pero no la reimplementa.

## 3. Recorrido del usuario del módulo

### Antes de la prueba

1. Mostrar instrucciones de la prueba de demostración o instrucciones aprobadas.
2. Preparar pantalla, distancia o simulador.
3. Esperar que el usuario presione **Comenzar**.

### Durante la prueba

1. Indicar qué ojo se está evaluando.
2. Registrar cada resultado ficticio.
3. Permitir repetir un ojo cuando la prueba quede incompleta.

### Después de la prueba

1. Mostrar resultados de ambos ojos.
2. Permitir **Confirmar** o **Repetir**.
3. Guardar solamente después de confirmar.

## 4. Responsabilidades del módulo

- Crear schemas y simulador.
- Implementar `POST` y `GET` de Vista.
- Validar resultados por ojo y distancia.
- Guardar en `ResultadoModulo`.
- Construir pantalla Vista.
- Escribir pruebas automáticas.
- Documentar investigación clínica propia en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `dispositivo_id` | `int` | Sí |
| `origen` | `str` | Sí |
| `data` | `DatosVista` | Sí |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `VISTA-001`
- `tipo`: `VISTA`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 5** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad o formato | Obligatorio |
|---|---|---|---:|
| `prueba` | `str` | código acordado/documentado | Sí |
| `ojo_derecho` | `str` | resultado según prueba | Sí |
| `ojo_izquierdo` | `str` | resultado según prueba | Sí |
| `distancia_cm` | `float` | cm | Sí |

El formato definitivo se ajusta solamente cuando la investigación oficial y el contrato lo justifiquen.

## 7. Validaciones técnicas mínimas

- resultados de ambos ojos presentes;
- `prueba` y resultados como textos no vacíos;
- `distancia_cm` mayor que cero;
- IDs positivos;
- episodio y dispositivo existentes;
- no interpretar clínicamente los resultados dentro del schema/router.

## 8. Endpoints del módulo

```text
POST /api/v1/vista/resultados
GET  /api/v1/vista/resultados/{episodio_id}
```

## 9. Estructura recomendada

```text
app/modules/vista/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

El resultado utiliza `modulo = "vista"` y guarda sus datos en `data_json`.

## 11. Frontend propio del módulo

Consultar `FRONTEND_BASE_Y_FLUJO.md`. La pantalla Vista debe:

- mostrar instrucciones y distancia de trabajo cuando corresponda;
- indicar ojo evaluado;
- mostrar resultados técnicos de ambos ojos;
- permitir repetir cuando una captura quede incompleta;
- confirmar antes de realizar el `POST`;
- volver al panel del episodio.

Archivos sugeridos:

```text
app/templates/modulos/vista.html
app/static/js/vista.js
```

## 12. Investigación clínica propia del grupo

El Grupo 5 investiga exclusivamente Vista: prueba, condiciones, distancia, lateralidad, población, unidades/escala y criterios oficiales candidatos.

Toda regla o criterio se registra en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. La tarea transversal del motor no autoriza al grupo a completar o seleccionar reglas clínicas de los demás módulos.

## 13. Tarea transversal — Motor de reglas y clasificación

### Objetivo

Separar claramente la información clínica aprobada de la lógica de software que la ejecuta.

```text
Fichas de reglas documentadas
          ↓
     Motor de reglas
          ↓
Resultados persistidos del episodio
          ↓
Resultado técnico de evaluación
          ↓
Clasificación preventiva
```

### Requisitos del motor

El motor debe:

1. recibir o consultar resultados ya guardados;
2. identificar la regla y versión que se pretende usar;
3. verificar su estado de activación;
4. impedir uso real de reglas no aprobadas/activas;
5. permitir `REGLAS_DE_PRUEBA_NO_CLINICAS` únicamente en desarrollo/tests;
6. detectar datos obligatorios faltantes;
7. ejecutar comparaciones o condiciones simples sin modificar la fuente;
8. devolver el resultado técnico necesario para clasificar;
9. conservar identificador y versión utilizados;
10. no reescribir resultados históricos.

La información sobre fuente, organismo, página, población, diferencias y aprobación se toma de `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`; no se redefine en el código ni en esta ficha.

### Endpoints de clasificación

```text
POST /api/v1/episodios/{episodio_id}/clasificar
GET  /api/v1/episodios/{episodio_id}/clasificacion
```

### Persistencia de clasificación

El grupo puede crear un modelo auxiliar con revisión docente. Debe conservar como mínimo:

- episodio;
- nivel/resultado de priorización;
- fecha/hora;
- identificador de regla o conjunto de reglas;
- versión;
- estado de la clasificación;
- observación técnica opcional.

### Reglas funcionales

- la clasificación toma datos desde SQLite, no desde valores que estén solamente en pantalla;
- si faltan datos obligatorios, devolver estado `INCOMPLETA` o equivalente acordado;
- si existe conflicto de fuentes sin decisión profesional registrada, no elegir automáticamente;
- color/nivel no se presenta como diagnóstico;
- una clasificación histórica conserva la versión aplicada.

### Frontend transversal

Crear una pantalla de clasificación/procesamiento que muestre:

- episodio;
- estado del procesamiento;
- datos faltantes si los hay;
- nivel solo cuando corresponda;
- identificador/versión de regla en modo técnico;
- advertencia preventiva;
- error o pendiente cuando una regla no puede aplicarse.

### Pruebas transversales

- regla ficticia de prueba ejecutada;
- regla no habilitada rechazada para uso real;
- datos faltantes;
- clasificación persistida con versión;
- consulta posterior;
- conflicto no resuelto automáticamente;
- historia previa no cambia al modificar una versión futura.

## 14. Pruebas mínimas del grupo

1. Vista válida.
2. Falta de resultado de un ojo.
3. Distancia incorrecta.
4. Prueba vacía.
5. Episodio inexistente.
6. Persistencia/consulta de Vista.
7. Regla ficticia de prueba.
8. Regla clínica no habilitada rechazada.
9. Datos faltantes → clasificación incompleta.
10. Clasificación persistida con versión.
11. Conflicto no resuelto automáticamente.
12. **Repetir/Confirmar** en Vista.

## 15. Criterios de aceptación

- Módulo Vista completo e integrado.
- Investigación de Vista documentada en la ficha clínica correspondiente.
- Motor desacoplado de los seis módulos.
- Motor consume resultados persistidos.
- Clasificación guarda regla/versión.
- No selecciona automáticamente entre fuentes en conflicto.
- Pantalla de clasificación funcional.
- Pruebas completas.
- Ninguna regla clínica se activa sin el estado requerido.

## 16. Entregables específicos

- backend/frontend de Vista;
- motor de reglas;
- endpoints y persistencia de clasificación;
- pantalla de clasificación;
- pruebas unitarias y de integración;
- documentación de interfaz del motor para los demás grupos;
- evidencias Swagger/Pytest;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` del módulo Vista.

## 17. No debe modificar

- resultados históricos;
- contratos de otros módulos;
- fuentes, condiciones o versiones documentadas por otros grupos;
- modelos comunes sin autorización;
- frontend base del Grupo 4 sin coordinación;
- informe del Grupo 6 salvo acuerdo de integración.

## 18. Estado clínico durante el desarrollo

El motor puede probarse con reglas claramente no clínicas. La habilitación de cualquier regla real depende exclusivamente del estado registrado en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
