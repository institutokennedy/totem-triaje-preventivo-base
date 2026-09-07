# Ficha del Grupo 1 — Signos vitales

**Módulo de medición:** signos vitales  
**Responsabilidad transversal:** identificación y registro del paciente  
**Frontend transversal:** inicio, búsqueda por DNI y registro  
**Historias relacionadas:** HU-01, HU-02, HU-05 y HU-13

## 0. Documentos que el grupo debe consultar

Antes de comenzar y durante las entregas, esta ficha se usa junto con:

- `CONTRATO_API_V1.md`: campos comunes, endpoints, respuestas y restricciones de integración.
- `PLAN_ENTREGAS_PARCIALES.md`: orden de entregas y evidencias requeridas.
- `FRONTEND_BASE_Y_FLUJO.md`: flujo común del frontend y responsabilidades de navegación.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`: única plantilla para documentar investigación, fuentes, reglas y aprobación profesional.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`: visión funcional general e historias de usuario.

Esta ficha detalla **qué debe hacer el Grupo 1**. No reemplaza los documentos anteriores.

## 1. Objetivo del grupo

Desarrollar el módulo que recibe y guarda presión arterial, frecuencia cardíaca, temperatura y saturación de oxígeno dentro de un episodio. Además, el grupo completa la identificación del paciente por DNI y la interfaz inicial de búsqueda/registro.

El módulo registra datos técnicos. No decide si un valor es normal, anormal o peligroso y no produce diagnósticos.

## 2. Punto de partida del repositorio

El repositorio ya incluye:

- modelo `Paciente`;
- `POST /api/v1/pacientes`;
- `GET /api/v1/pacientes`;
- `GET /api/v1/pacientes/{paciente_id}`;
- control de DNI duplicado en el alta;
- modelo `ResultadoModulo`;
- servicio compartido para guardar y consultar resultados.

El grupo **no rehace** esas funciones. Debe comprenderlas, utilizarlas y completar lo asignado.

La infraestructura común también incluye el alta y consulta de dispositivos mediante API. Cada grupo la utiliza para obtener el `dispositivo_id` de sus pruebas, pero no la reimplementa.

## 3. Recorrido del usuario del módulo

### Antes del sensado

1. Mostrar instrucciones para cada medición.
2. Pedir al usuario que se ubique y prepare el dispositivo.
3. Esperar que presione **Comenzar**.

### Durante el sensado

1. Mostrar qué signo vital se está capturando.
2. Recibir los valores del sensor o simulador.
3. Informar un error técnico y permitir repetir si no llegan datos.

### Después del sensado

1. Mostrar todos los valores capturados.
2. Permitir **Confirmar** o **Repetir**.
3. Enviar el resultado a la API únicamente después de confirmar.

## 4. Responsabilidades del módulo

- Crear `schemas.py` para signos vitales.
- Crear `simulator.py` con datos ficticios.
- Implementar los endpoints `POST` y `GET` del módulo.
- Validar tipos, campos obligatorios e identificadores.
- Guardar mediante el servicio común de `ResultadoModulo`.
- Recuperar resultados por episodio.
- Construir la pantalla propia del módulo.
- Escribir pruebas automáticas con Pytest.
- Documentar la investigación clínica del módulo mediante `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio | Ejemplo |
|---|---|---:|---|
| `episodio_id` | `int` | Sí | `15` |
| `dispositivo_id` | `int` | Sí | `1` |
| `origen` | `str` | Sí | `"SIMULADOR"` |
| `data` | `DatosSignosVitales` | Sí | Objeto con cinco valores |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `SV-001`
- `tipo`: `SIGNOS_VITALES`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 1** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad del contrato | Obligatorio |
|---|---|---|---:|
| `presion_sistolica` | `float` | mmHg | Sí |
| `presion_diastolica` | `float` | mmHg | Sí |
| `frecuencia_cardiaca` | `float` | lpm | Sí |
| `temperatura` | `float` | °C | Sí |
| `saturacion_oxigeno` | `float` | % | Sí |

Las unidades forman parte del contrato técnico inicial. Cualquier condición clínica, población, procedimiento o regla asociada debe quedar documentada en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` antes de incorporarse como lógica clínica.

## 7. Validaciones técnicas mínimas

- Los cinco valores deben estar presentes.
- Los valores deben ser números, no textos.
- No se aceptan `NaN` ni `Infinity`.
- `episodio_id` y `dispositivo_id` deben ser enteros mayores que cero.
- `origen` debe ser `SENSOR` o `SIMULADOR`.
- El episodio debe existir antes de guardar.
- El dispositivo debe existir antes de guardar.
- No se aplican rangos ni umbrales clínicos dentro del schema.

## 8. Endpoints del módulo

```text
POST /api/v1/signos-vitales/resultados
GET  /api/v1/signos-vitales/resultados/{episodio_id}
```

El `POST` guarda solamente una captura confirmada. El `GET` devuelve resultados del módulo para el episodio indicado.

## 9. Estructura recomendada

```text
app/modules/signos_vitales/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

El servicio común debe crear un `ResultadoModulo` con:

- `episodio_id` recibido;
- `dispositivo_id` recibido;
- `modulo = "signos_vitales"`;
- `data_json` con los cinco valores;
- `fecha_hora` generada por el servidor.

No se crea una tabla propia para signos vitales en esta etapa.

## 11. Frontend propio del módulo

El comportamiento común está definido en `FRONTEND_BASE_Y_FLUJO.md`. El Grupo 1 debe implementar su pantalla específica para:

- mostrar instrucciones de medición;
- mostrar cuál dato se está capturando;
- mostrar el conjunto de valores obtenidos sin interpretación clínica;
- permitir **Repetir** sin guardar;
- permitir **Confirmar** y recién entonces ejecutar el `POST`;
- mostrar errores de API de forma comprensible;
- volver al panel del episodio después del guardado.

Archivos sugeridos:

```text
app/templates/modulos/signos_vitales.html
app/static/js/signos_vitales.js
```

## 12. Investigación clínica propia del grupo

El Grupo 1 investiga **exclusivamente signos vitales**. Debe localizar documentación oficial pertinente sobre procedimiento, condiciones de medición, población, unidades y criterios que eventualmente puedan intervenir en la orientación preventiva.

Toda fuente, criterio o regla candidata se registra en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. **No duplicar en esta ficha** la información de fuente, páginas, aprobación o estado de activación.

## 13. Tarea transversal — Identificación y registro del paciente

### Objetivo

Completar el recorrido de HU-01 y HU-02 aprovechando los endpoints de pacientes ya existentes.

### Backend pendiente

Implementar:

```text
GET /api/v1/pacientes/dni/{dni}
```

Debe:

1. recibir el DNI;
2. buscar al paciente;
3. devolver sus datos si existe;
4. devolver `404` si no existe;
5. conservar el control de duplicados del `POST /api/v1/pacientes`;
6. utilizar únicamente identidades ficticias en desarrollo y pruebas.

### Datos del registro

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `dni` | `str` | Sí |
| `nombre` | `str` | Sí |
| `apellido` | `str` | Sí |
| `fecha_nacimiento` | `date` | Sí |
| `email` | `str` | No |
| `telefono` | `str` | No |

### Frontend transversal

Crear/completar la pantalla de inicio e identificación:

```text
Inicio → Ingresar DNI → Buscar
                    ↙          ↘
                 existe       no existe
                   ↓             ↓
             mostrar datos    registrar
                   └──────┬──────┘
                          ↓
                    continuar
```

Debe mostrar el conflicto `409` cuando se intenta registrar un DNI ya existente.

### Pruebas transversales

- paciente existente por DNI;
- paciente inexistente;
- registro válido;
- DNI duplicado;
- datos obligatorios faltantes;
- navegación desde identificación hacia selección de circuito.

## 14. Pruebas mínimas del grupo

1. Resultado de signos vitales válido.
2. Temperatura enviada como texto.
3. Falta de saturación de oxígeno.
4. Identificadores menores o iguales que cero.
5. Episodio inexistente.
6. Dispositivo inexistente.
7. Persistencia y consulta por episodio.
8. Paciente existente por DNI.
9. Paciente inexistente por DNI.
10. Registro correcto de paciente ficticio.
11. DNI ficticio duplicado.
12. **Repetir** no guarda y **Confirmar** sí guarda.

## 15. Criterios de aceptación

- Los endpoints del módulo aparecen en Swagger.
- El simulador produce el JSON acordado.
- FastAPI devuelve errores coherentes para datos incorrectos.
- El resultado confirmado queda en `ResultadoModulo`.
- La consulta devuelve solamente resultados del episodio solicitado.
- La búsqueda por DNI funciona.
- El registro evita duplicaciones.
- La pantalla de identificación y la pantalla del módulo se integran al flujo común.
- Todas las pruebas pasan.
- El módulo no contiene interpretación clínica no aprobada.

## 16. Entregables específicos

- `schemas.py`;
- `simulator.py`;
- `router.py`;
- `test_router.py`;
- plantilla HTML y JavaScript del módulo;
- búsqueda por DNI;
- interfaz de identificación/registro;
- evidencia Swagger;
- evidencia Pytest;
- una o más `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` completadas según corresponda.

## 17. No debe modificar

- `database.py` y configuración SQLite;
- modelos comunes de SQLModel;
- servicio compartido de resultados;
- rutas de otros grupos;
- frontend base común del Grupo 4 sin coordinación;
- fuentes, umbrales o versiones de reglas aprobadas;
- resultados históricos.

## 18. Estado clínico durante el desarrollo

Mientras una regla no tenga la documentación y aprobación exigidas en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`, permanece inactiva. Los datos de simulación y prueba son ficticios.
