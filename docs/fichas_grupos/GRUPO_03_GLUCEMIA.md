# Ficha del Grupo 3 — Glucemia

**Módulo de medición:** glucemia  
**Responsabilidad transversal:** consentimiento y control de continuidad del episodio  
**Frontend transversal:** consentimiento y habilitación/bloqueo del recorrido  
**Historias relacionadas:** HU-04 y HU-10

## 0. Documentos que el grupo debe consultar

- `CONTRATO_API_V1.md`.
- `PLAN_ENTREGAS_PARCIALES.md`.
- `FRONTEND_BASE_Y_FLUJO.md`.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`.

## 1. Objetivo del grupo

Desarrollar un módulo que reciba un valor ficticio de glucemia, su unidad y el método declarado, lo valide técnicamente y lo guarde dentro de un episodio. Además, el grupo implementará el consentimiento del episodio y el control funcional que habilita o bloquea la continuidad del recorrido según la decisión registrada.

El módulo no determina por sí mismo si un valor es normal, elevado o bajo.

## 2. Punto de partida del repositorio

Ya existen:

- modelo `Dispositivo`;
- `POST /api/v1/dispositivos`;
- `GET /api/v1/dispositivos`;
- `GET /api/v1/dispositivos/{dispositivo_id}`;
- modelo `ResultadoModulo` y servicio común;
- episodio con estado inicial.

El alta y consulta de dispositivos son infraestructura común entregada. El Grupo 3 debe utilizarlas, pero no modificarlas ni reimplementarlas. La tarea transversal pendiente del grupo es el consentimiento y el control de continuidad del recorrido.

## 3. Recorrido del usuario del módulo

### Antes del sensado

1. Mostrar instrucciones para la demostración o las instrucciones aprobadas.
2. Identificar método de captura o simulación.
3. Esperar que el usuario presione **Comenzar**.

### Durante el sensado

1. Mostrar que se espera el valor.
2. Recibir el dato del sensor o simulador.
3. Informar una falla técnica y permitir repetir.

### Después del sensado

1. Mostrar valor, unidad y método.
2. Permitir **Confirmar** o **Repetir**.
3. Guardar únicamente después de confirmar.

## 4. Responsabilidades del módulo

- Crear `schemas.py` de glucemia.
- Crear `simulator.py`.
- Implementar `POST` y `GET` del módulo.
- Validar valor, unidad y método.
- Guardar con `ResultadoModulo`.
- Construir la pantalla de glucemia.
- Escribir pruebas automáticas.
- Documentar investigación clínica propia con `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `dispositivo_id` | `int` | Sí |
| `origen` | `str` | Sí |
| `data` | `DatosGlucemia` | Sí |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `GLU-001`
- `tipo`: `GLUCEMIA`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 3** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad o formato | Obligatorio |
|---|---|---|---:|
| `valor` | `float` | según `unidad` | Sí |
| `unidad` | `str` | `mg/dL` o `mmol/L` | Sí |
| `metodo` | `str` | método declarado o `SIMULADO` | Sí |

La API no convierte automáticamente unidades.

## 7. Validaciones técnicas mínimas

- `valor` debe ser un número finito.
- `unidad` debe pertenecer a las opciones técnicas acordadas.
- `metodo` no puede estar vacío.
- Los identificadores deben ser mayores que cero.
- Episodio y dispositivo deben existir.
- No se comparan valores con umbrales clínicos dentro del módulo.

## 8. Endpoints del módulo

```text
POST /api/v1/glucemia/resultados
GET  /api/v1/glucemia/resultados/{episodio_id}
```

## 9. Estructura recomendada

```text
app/modules/glucemia/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

`ResultadoModulo` debe guardar `modulo = "glucemia"` y serializar `valor`, `unidad` y `metodo` en `data_json`.

## 11. Frontend propio del módulo

Consultar el flujo común en `FRONTEND_BASE_Y_FLUJO.md`. La pantalla debe:

- mostrar instrucciones;
- mostrar estado de medición/simulación;
- mostrar valor, unidad y método sin interpretación;
- permitir **Repetir** sin guardar;
- permitir **Confirmar** y realizar el `POST`;
- mostrar errores técnicos/API.

Archivos sugeridos:

```text
app/templates/modulos/glucemia.html
app/static/js/glucemia.js
```

## 12. Investigación clínica propia del grupo

El Grupo 3 investiga exclusivamente las especificaciones de glucemia que correspondan al proyecto: procedimiento, método, unidades, población, condiciones y criterios candidatos.

Todo hallazgo se registra en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. La ficha de grupo no debe duplicar ni reemplazar la trazabilidad clínica.

## 13. Tarea transversal — Consentimiento y control de continuidad

### A. Consentimiento

#### Objetivo

Implementar HU-04: registrar aceptación o rechazo dentro de un episodio antes de continuar con las mediciones que requieran autorización.

#### Endpoints a desarrollar

```text
POST /api/v1/consentimientos
GET  /api/v1/consentimientos/{episodio_id}
```

#### Datos mínimos

| Campo | Tipo | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `version` | `str` | Sí |
| `aceptado` | `bool` | Sí |
| `observacion` | `str` | No |

Fecha/hora se genera en el servidor.

#### Persistencia

El grupo puede crear un modelo auxiliar simple `Consentimiento` con revisión docente, sin modificar los cuatro modelos comunes.

Debe quedar asociado a un episodio y conservar versión, respuesta y fecha/hora.

#### Reglas funcionales

- episodio debe existir;
- si se registra rechazo, la interfaz no debe permitir avanzar a los módulos que dependan del consentimiento;
- no borrar el registro histórico de la decisión;
- la versión del texto debe quedar guardada.

#### Frontend de consentimiento

Debe:

- mostrar el texto/version vigente suministrado para la práctica;
- permitir aceptar o rechazar;
- guardar la decisión;
- informar claramente si el recorrido continúa o queda detenido.

### B. Control de continuidad del recorrido

Una vez registrado el consentimiento, la aplicación debe utilizar esa decisión para controlar el avance del episodio.

#### Si `aceptado = true`

- permitir continuar hacia el panel o los módulos habilitados;
- mantener disponible la consulta del consentimiento registrado;
- evitar solicitar nuevamente el consentimiento dentro del mismo episodio salvo que el diseño funcional indique una nueva versión.

#### Si `aceptado = false`

- conservar el rechazo en la base;
- impedir el acceso a las mediciones que dependan del consentimiento;
- mostrar un mensaje funcional claro, sin borrar el episodio ni inventar información;
- coordinar con el Grupo 2 cualquier cambio de estado del episodio, porque la gestión de estados pertenece a ese grupo.

#### Frontend transversal

La pantalla debe:

- mostrar la versión del consentimiento;
- permitir aceptar o rechazar;
- enviar la decisión a la API;
- consultar la decisión cuando se vuelva a abrir el episodio;
- habilitar la continuidad si fue aceptado;
- bloquearla si fue rechazado;
- mostrar errores de API de forma comprensible.

### Pruebas transversales

- consentimiento aceptado;
- consentimiento rechazado;
- episodio inexistente;
- consulta de consentimiento;
- aceptación habilita la continuidad;
- rechazo bloquea la continuidad;
- recarga del episodio conserva la decisión.

## 14. Pruebas mínimas del grupo

1. Resultado de glucemia válido.
2. Valor enviado como texto.
3. Unidad desconocida.
4. Falta de método.
5. Episodio inexistente.
6. Dispositivo inexistente.
7. Persistencia y consulta.
8. Consentimiento aceptado/rechazado.
9. Consentimiento aceptado habilita continuidad.
10. Consentimiento rechazado bloquea continuidad.
11. **Repetir** no guarda y **Confirmar** sí guarda.

## 15. Criterios de aceptación

- Módulo glucemia visible en Swagger y frontend.
- No convierte unidades silenciosamente.
- Resultado persiste en `ResultadoModulo`.
- Consentimiento queda asociado al episodio y conserva versión.
- Rechazo detiene el avance funcional correspondiente.
- Todas las pruebas pasan.
- No se emite diagnóstico ni se aplican reglas no aprobadas.

## 16. Entregables específicos

- archivos backend del módulo;
- HTML/JS de glucemia;
- endpoints y persistencia de consentimiento;
- pantalla de consentimiento y control de continuidad;
- evidencias Swagger/Pytest;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` para investigación del módulo.

## 17. No debe modificar

- configuración y modelos comunes;
- rutas de otros grupos;
- fuentes o reglas clínicas aprobadas;
- resultados históricos;
- frontend base del Grupo 4 sin coordinación;
- motor/clasificación del Grupo 5.

## 18. Estado clínico durante el desarrollo

Ninguna interpretación de glucemia se activa desde este módulo. La documentación clínica se gestiona exclusivamente mediante `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
