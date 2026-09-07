# Ficha del Grupo 2 — ECG

**Módulo de medición:** electrocardiograma  
**Responsabilidad transversal:** episodios, selección de circuito y estados  
**Frontend transversal:** selección de circuito y episodio activo  
**Historias relacionadas:** HU-03, HU-09 y HU-14

## 0. Documentos que el grupo debe consultar

- `CONTRATO_API_V1.md`.
- `PLAN_ENTREGAS_PARCIALES.md`.
- `FRONTEND_BASE_Y_FLUJO.md`.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`.

Esta ficha especifica el trabajo del Grupo 2; las reglas comunes y clínicas se consultan en esos documentos.

## 1. Objetivo del grupo

Desarrollar un módulo que reciba una serie de muestras ficticias de ECG y las guarde dentro de un episodio. Como responsabilidad transversal, el grupo completa la selección del circuito y la gestión básica de estados del episodio.

El ECG se almacena como registro técnico. El módulo no interpreta ritmo, morfología ni produce diagnósticos.

## 2. Punto de partida del repositorio

Ya existen:

- modelo `EpisodioAtencion`;
- `POST /api/v1/episodios`;
- `GET /api/v1/episodios`;
- `GET /api/v1/episodios/{episodio_id}`;
- comprobación de paciente existente antes de crear episodio;
- estado inicial `INICIADO`;
- persistencia común de resultados.

El grupo no rehace esos endpoints: los utiliza y mejora lo asignado.

La infraestructura común también incluye el alta y consulta de dispositivos mediante API. Cada grupo la utiliza para obtener el `dispositivo_id` de sus pruebas, pero no la reimplementa.

## 3. Recorrido del usuario del módulo

### Antes del sensado

1. Mostrar instrucciones de colocación definidas para la demostración o por una fuente aprobada.
2. Verificar que el simulador o dispositivo esté disponible.
3. Esperar que el usuario presione **Comenzar**.

### Durante el sensado

1. Mostrar que la captura está en curso.
2. Recibir una lista de muestras.
3. Detectar lista vacía o interrupción técnica y permitir repetir.

### Después del sensado

1. Mostrar un resumen técnico de la captura.
2. Permitir **Confirmar** o **Repetir**.
3. Enviar el resultado solamente después de confirmar.

## 4. Responsabilidades del módulo

- Definir schemas explícitos para ECG.
- Crear un simulador de señal ficticia.
- Implementar los endpoints `POST` y `GET` del módulo.
- Validar lista de muestras, unidad y frecuencia de muestreo.
- Guardar mediante `ResultadoModulo`.
- Recuperar resultados por episodio.
- Construir la pantalla ECG.
- Escribir pruebas automáticas.
- Documentar investigación clínica propia mediante `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `dispositivo_id` | `int` | Sí |
| `origen` | `str` | Sí |
| `data` | `DatosECG` | Sí |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `ECG-001`
- `tipo`: `ECG`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 2** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad | Obligatorio |
|---|---|---|---:|
| `frecuencia_muestreo_hz` | `int` | Hz | Sí |
| `muestras` | `list[float]` | Según `unidad` | Sí |
| `unidad` | `str` | `mV` o `ADC` | Sí |

ECG tiene más datos que otros módulos porque necesita una lista de muestras. Para pruebas iniciales la lista puede ser pequeña.

## 7. Validaciones técnicas mínimas

- `frecuencia_muestreo_hz` debe ser un entero mayor que cero.
- `muestras` debe contener al menos un número.
- Cada muestra debe ser un número finito.
- `unidad` debe ser una de las opciones acordadas en el contrato técnico.
- Los identificadores deben ser mayores que cero.
- Episodio y dispositivo deben existir.
- No se analiza el ritmo ni la forma clínica de la señal.

## 8. Endpoints del módulo

```text
POST /api/v1/ecg/resultados
GET  /api/v1/ecg/resultados/{episodio_id}
```

## 9. Estructura recomendada

```text
app/modules/ecg/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

`ResultadoModulo` debe guardar:

- `modulo = "ecg"`;
- episodio;
- dispositivo;
- lista de muestras y metadatos serializados en `data_json`;
- fecha/hora del servidor.

En la primera etapa se usan listas pequeñas; archivos o señales extensas se incorporan solamente si se acuerda en integración.

## 11. Frontend propio del módulo

El flujo común se consulta en `FRONTEND_BASE_Y_FLUJO.md`. La pantalla ECG debe:

- mostrar instrucciones;
- informar que la captura está en curso;
- mostrar cantidad de muestras, frecuencia y unidad como resumen técnico;
- no intentar interpretar la señal;
- permitir **Repetir** sin guardar;
- permitir **Confirmar** y ejecutar el `POST`;
- informar errores de dispositivo o API.

Archivos sugeridos:

```text
app/templates/modulos/ecg.html
app/static/js/ecg.js
```

## 12. Investigación clínica propia del grupo

El Grupo 2 investiga exclusivamente las especificaciones de ECG que correspondan al proyecto: procedimiento, condiciones de captura, población, unidades, requisitos técnicos y cualquier criterio oficial candidato a ser utilizado.

Toda regla, procedimiento o condición clínica se registra en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. No se repiten en esta ficha los campos de trazabilidad ni el circuito de aprobación.

## 13. Tarea transversal — Episodios, circuito y estados

### Objetivo

Completar HU-03 utilizando la implementación existente de episodios.

### Endpoint existente a perfeccionar

```text
POST /api/v1/episodios
```

También se utilizan:

```text
GET /api/v1/episodios
GET /api/v1/episodios/{episodio_id}
```

### Entrada

| Campo | Tipo Python | Obligatorio | Valores admitidos |
|---|---|---:|---|
| `paciente_id` | `int` | Sí | paciente ficticio existente |
| `tipo_circuito` | `str` | Sí | `GUARDIA` o `COMPLETO` |

### Trabajo pendiente

- validar explícitamente los tipos de circuito admitidos;
- conservar la asociación con un paciente existente;
- devolver el identificador del episodio;
- mostrar tipo de circuito, fecha/hora y estado al consultar;
- implementar una forma simple y controlada de cambiar el estado cuando el proyecto lo requiera;
- impedir transiciones imposibles acordadas por el equipo docente;
- no inventar estados clínicos: los estados son funcionales del proceso.

Estados funcionales iniciales que pueden usarse como referencia técnica, sujetos al documento funcional:

```text
INICIADO → EN_MEDICION → EN_PROCESAMIENTO / CLASIFICADO → INFORME_GENERADO → FINALIZADO
```

No es obligatorio implementar todos en la primera entrega transversal. Deben incorporarse por etapas según el plan.

### Frontend transversal

Crear/completar:

- pantalla de selección `GUARDIA` / `COMPLETO`;
- creación del episodio;
- visualización de episodio activo;
- visualización de ID, paciente, circuito y estado;
- paso al panel del episodio.

### Pruebas transversales

- creación con paciente existente;
- paciente inexistente;
- circuito válido;
- circuito desconocido;
- consulta por ID;
- cambio de estado permitido;
- rechazo de transición inválida cuando esa lógica se incorpore.

## 14. Pruebas mínimas del grupo

1. ECG válido con varias muestras.
2. Lista de muestras vacía.
3. Muestras enviadas como texto.
4. Falta de unidad.
5. Frecuencia de muestreo técnicamente inválida.
6. Episodio inexistente.
7. Dispositivo inexistente.
8. Persistencia y consulta.
9. Creación de episodio válida.
10. Paciente inexistente.
11. Tipo de circuito desconocido.
12. Flujo **Repetir/Confirmar**.

## 15. Criterios de aceptación

- Endpoints ECG visibles en Swagger.
- Lista de muestras validada con Pydantic.
- Simulador ficticio repetible.
- Resultado asociado al episodio correcto.
- Tipo de circuito validado.
- Episodio creado solo para paciente existente.
- Pantalla ECG y pantalla de circuito integradas.
- Pruebas aprobadas.
- No se interpreta clínicamente el ECG.

## 16. Entregables específicos

- archivos del módulo;
- HTML/JS de ECG;
- mejora de episodios/circuito/estados;
- pantalla de circuito y episodio activo;
- evidencias Swagger y Pytest;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` según investigación del módulo.

## 17. No debe modificar

- modelos comunes y configuración de base;
- rutas de otros grupos;
- servicio compartido de resultados;
- reglas clínicas aprobadas;
- frontend común del Grupo 4 sin coordinación;
- resultados históricos.

## 18. Estado clínico durante el desarrollo

La señal y datos de simulación son ficticios. Una condición clínica solo puede incorporarse siguiendo `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
