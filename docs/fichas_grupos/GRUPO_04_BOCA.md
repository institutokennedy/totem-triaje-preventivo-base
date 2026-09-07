# Ficha del Grupo 4 — Boca

**Módulo de medición:** evaluación técnica de boca  
**Responsabilidad transversal:** frontend base y navegación común  
**Frontend transversal:** `base.html`, estilos, menú y panel del episodio  
**Historias relacionadas:** HU-16 y requisitos transversales de interfaz/integración

## 0. Documentos que el grupo debe consultar

- `CONTRATO_API_V1.md`.
- `PLAN_ENTREGAS_PARCIALES.md`.
- `FRONTEND_BASE_Y_FLUJO.md`.
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.
- `GUIA_HISTORIAS_USUARIO_DER_BACKLOG_V2.md`.

## 1. Objetivo del grupo

Desarrollar un módulo que registre una referencia a una imagen ficticia de cavidad oral y una observación técnica sobre la captura. Además, el grupo construirá la estructura visual común que usan los demás grupos para integrar sus pantallas.

El módulo no identifica enfermedades ni reemplaza una evaluación odontológica profesional.

## 2. Punto de partida del repositorio

El backend común ya permite trabajar con pacientes, episodios, dispositivos y resultados. El frontend base todavía debe ser desarrollado por estudiantes. Esa responsabilidad corresponde al Grupo 4.

El Grupo 4 no debe construir las pantallas específicas de signos vitales, ECG, glucemia, vista u oído: debe proporcionar el marco común para integrarlas.

La infraestructura común también incluye el alta y consulta de dispositivos mediante API. Cada grupo la utiliza para obtener el `dispositivo_id` de sus pruebas, pero no la reimplementa.

## 3. Recorrido del usuario del módulo

### Antes de la captura

1. Mostrar instrucciones sencillas.
2. Verificar cámara o simulador.
3. Esperar que el usuario presione **Comenzar**.

### Durante la captura

1. Mostrar vista previa o una imagen de demostración.
2. Comprobar que exista una referencia de imagen.
3. Permitir repetir si la captura técnica falla.

### Después de la captura

1. Mostrar la imagen seleccionada o su referencia.
2. Permitir **Confirmar** o **Repetir**.
3. Guardar la referencia después de confirmar.

## 4. Responsabilidades del módulo

- Crear schemas y simulador.
- Implementar endpoints `POST` y `GET`.
- Validar nombre y extensión de imagen ficticia.
- Guardar mediante el servicio común.
- Construir la pantalla Boca.
- Escribir pruebas automáticas.
- Documentar investigación clínica propia en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`.

## 5. Datos comunes de entrada

| Campo | Tipo Python | Obligatorio |
|---|---|---:|
| `episodio_id` | `int` | Sí |
| `dispositivo_id` | `int` | Sí |
| `origen` | `str` | Sí |
| `data` | `DatosBoca` | Sí |

### Cómo obtener `dispositivo_id`

La gestión de dispositivos ya está resuelta por el repositorio base. El grupo **no debe programar** estos endpoints:

```text
POST /api/v1/dispositivos
GET  /api/v1/dispositivos
GET  /api/v1/dispositivos/{dispositivo_id}
```

Para las pruebas del módulo se recomienda registrar un dispositivo ficticio con:

- `codigo`: `BOCA-001`
- `tipo`: `BOCA`
- `nombre`: un nombre descriptivo elegido por el grupo.

SQLite genera el `id`. Ese valor se utiliza luego en el campo `dispositivo_id`. **No existe un ID fijo para el Grupo 4** y el número puede ser distinto en cada computadora o base de datos.

Si el dispositivo ya fue creado, el grupo debe usar `GET /api/v1/dispositivos`, localizarlo por `codigo` y recuperar su `id`. En el frontend final, el paciente no debe escribir este número manualmente.

## 6. Datos propios de `data`

| Campo | Tipo Python | Unidad o formato | Obligatorio |
|---|---|---|---:|
| `nombre_imagen` | `str` | nombre con extensión admitida | Sí |
| `observacion_tecnica` | `str` | texto breve | No |

En la primera etapa se utilizan nombres/referencias de archivos ficticios. La carga real de imágenes se incorpora solamente si el proyecto la habilita en una etapa posterior.

## 7. Validaciones técnicas mínimas

- `nombre_imagen` debe ser texto y no vacío.
- Extensión admitida: `.jpg`, `.jpeg` o `.png`.
- `observacion_tecnica` no contiene diagnósticos.
- Los identificadores deben ser mayores que cero.
- Episodio y dispositivo deben existir.
- No se analiza clínicamente la imagen dentro del módulo.

## 8. Endpoints del módulo

```text
POST /api/v1/boca/resultados
GET  /api/v1/boca/resultados/{episodio_id}
```

## 9. Estructura recomendada

```text
app/modules/boca/
├── router.py
├── schemas.py
├── simulator.py
└── test_router.py
```

## 10. Almacenamiento

El resultado utiliza `modulo = "boca"` y guarda la referencia de imagen/observación dentro de `data_json`.

## 11. Frontend propio del módulo

Consultar `FRONTEND_BASE_Y_FLUJO.md` para el flujo común. La pantalla Boca debe:

- mostrar instrucciones;
- mostrar vista previa o referencia de captura ficticia;
- indicar error técnico de captura;
- permitir **Repetir**;
- confirmar antes de guardar;
- no mostrar interpretación clínica.

Archivos sugeridos:

```text
app/templates/modulos/boca.html
app/static/js/boca.js
```

## 12. Investigación clínica propia del grupo

El Grupo 4 investiga exclusivamente las condiciones y especificaciones de evaluación/captura de cavidad oral que correspondan al proyecto.

Fuentes, procedimientos, criterios y reglas candidatas se documentan en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. No deben copiarse ni resumirse aquí como si estuvieran aprobados.

## 13. Tarea transversal — Frontend base y navegación

### Objetivo

Construir el marco común de interfaz para que los seis módulos puedan integrarse sin crear seis sistemas visuales diferentes.

### Archivos comunes a desarrollar

Como mínimo:

```text
app/templates/base.html
app/templates/inicio.html
app/templates/circuito.html
app/templates/episodio.html
app/templates/resumen.html
app/static/css/estilos.css
app/static/js/app.js
```

La ubicación exacta puede ajustarse con el docente, pero debe conservar una estructura común.

### Funciones del frontend base

- encabezado/título común;
- navegación consistente;
- zona para mensajes de éxito/error;
- paciente identificado visible cuando corresponda;
- episodio activo visible;
- circuito seleccionado visible;
- panel con accesos a módulos;
- indicador simple de módulos pendientes/realizados;
- botón de volver al panel;
- enlace al resumen final cuando esté disponible.

### Panel del episodio

Debe permitir integrar botones/enlaces para:

- Signos vitales;
- ECG;
- Glucemia;
- Boca;
- Vista;
- Oído;
- Clasificación cuando corresponda;
- Informe/resumen final.

El Grupo 4 define estilos y estructura, pero **cada grupo es responsable del contenido y JavaScript de su propia pantalla**.

### Contrato de integración visual

- los módulos deben heredar o reutilizar `base.html`;
- evitar CSS que rompa otras pantallas;
- no renombrar IDs, rutas o estructuras acordadas sin Pull Request;
- el panel recibe/usa el episodio activo y no pide escribir manualmente su ID;
- los errores de API deben poder mostrarse en un componente común;
- la navegación debe respetar el flujo de `FRONTEND_BASE_Y_FLUJO.md`.

### Pruebas/validaciones transversales

- navegación Inicio → identificación → circuito → panel;
- panel muestra paciente/episodio;
- acceso a cada módulo disponible;
- regreso al panel;
- diseño utilizable en pantalla del tótem;
- una pantalla de otro grupo integrada sin romper estilos;
- mensajes de error visibles.

## 14. Pruebas mínimas del grupo

1. Imagen ficticia válida.
2. Nombre numérico o tipo incorrecto.
3. Falta de nombre de imagen.
4. Extensión no admitida.
5. Episodio inexistente.
6. Persistencia y consulta.
7. **Repetir/Confirmar**.
8. Navegación del frontend base.
9. Integración de al menos una pantalla ajena.
10. Panel del episodio muestra contexto correcto.

## 15. Criterios de aceptación

- Endpoints Boca visibles en Swagger.
- Referencias de imagen validadas.
- Resultado asociado al episodio.
- Pantalla Boca funcional.
- `base.html` y estilos comunes disponibles.
- Panel del episodio permite integrar los seis módulos.
- Navegación común funciona sin pedir IDs manualmente al usuario final.
- Todas las pruebas pasan.
- No se incorpora interpretación odontológica no aprobada.

## 16. Entregables específicos

- backend del módulo Boca;
- HTML/JS del módulo Boca;
- frontend base común;
- CSS común;
- panel del episodio;
- documentación breve de cómo los demás grupos integran sus plantillas;
- evidencia de integración de una pantalla ajena;
- evidencias Swagger/Pytest;
- `FICHA_TRAZABILIDAD_REGLA_CLINICA.md` según investigación del módulo.

## 17. No debe modificar

- modelos y configuración común de base;
- schemas o endpoints de otros módulos;
- lógica clínica del Grupo 5;
- informe del Grupo 6;
- fuentes o reglas aprobadas;
- resultados históricos.

## 18. Estado clínico durante el desarrollo

La investigación clínica del módulo se registra en `FICHA_TRAZABILIDAD_REGLA_CLINICA.md`. La imagen y observaciones de prueba son ficticias.
