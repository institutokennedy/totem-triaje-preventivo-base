# Plantilla de trazabilidad de una regla clínica

**Proyecto:** Tótem de triaje preventivo  
**Estado inicial:** PENDIENTE DE DEFINICIÓN Y VALIDACIÓN CLÍNICA

Esta ficha debe completarse antes de entregar una regla a los estudiantes para su implementación. Una regla no puede activarse con campos obligatorios vacíos.

---

# Regla 1: Colocación de Electrodos

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-001 |
| Nombre breve | Colocación de Electrodos |
| Módulo relacionado | Módulo de Adquisición de Señal ECG |
| Variable utilizada | Derivaciones de extremidades (RA, LA, LL) |
| Unidad de medida | mV / Canales |
| Población de aplicación | Población general (adultos y pediátricos) |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de la Nación / AHA / IEC 60601-2-25 |
| Nombre completo del documento | Guías de Estandarización e Interpretación de Electrocardiografía |
| Versión o edición | Edición 2023 |
| Fecha de publicación | 2023 |
| URL oficial | [https\://www\.argentina.gob.ar/salud](https://www.argentina.gob.ar/salud) |
| Página | Págs. 15-18 |
| Tabla o apartado | Apartado 2.1: Posicionamiento de Derivaciones |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Verificación de la posición correcta de los 3 electrodos (RA, LA, LL) y ausencia de inversión de cables (ej. RA-LA). |
| Resultado o nivel asociado | Señal electrocardiográfica válida / Alerta de inversión de electrodos. |
| Acción indicada por la fuente | Validar trazado o solicitar reposicionamiento físico de los electrodos en el tótem de triaje. |
| Excepciones informadas | Amputaciones de miembros, temblor severo no controlable, dextrocardia. |
| Datos obligatorios para aplicarla | Impedancia de contacto de electrodos, canales RA, LA, LL. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Ninguna. Todas las guías estándar (AHA/IEC) coinciden en el código de colores y posicionamiento de electrodos de extremidades. |
| Decisión de la autoridad responsable | Aprobado sin modificaciones para el Tótem de Triaje Preventivo. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `ecg_signal_processor.py` \-\> `validate_electrode_placement()` |
| Grupo responsable | Grupo 1 \- Hardware e Integración de Sensores ESP32 |
| Datos de entrada | Señales analógicas RA, LA, LL (pines ADC ESP32) |
| Resultado esperado | Boolean (`True` \= Posición Correcta, `False` \= Inversión Detectada) |
| Pruebas automáticas asociadas | `test_electrode_inversion_unit.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado en Sprint 2 (Proyecto Integrador PIE 2026\) |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 2: Calidad e Integridad de Señal

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-002 |
| Nombre breve | Calidad e Integridad de Señal |
| Módulo relacionado | Módulo de Adquisición y Filtrado de Señal |
| Variable utilizada | Velocidad de barrido, Ganancia, Frecuencia de corte de filtros |
| Unidad de medida | mm/s, mm/mV, Hz |
| Población de aplicación | Población general |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de Córdoba / Sociedad Argentina de Cardiología (SAC) |
| Nombre completo del documento | Manual de Calidad e Interpretación Electrocardiográfica en Triaje |
| Versión o edición | 2da Edición |
| Fecha de publicación | 2024 |
| URL oficial | [https\://www\.cba.gov.ar/salud](https://www.cba.gov.ar/salud) |
| Página | Págs. 30-34 |
| Tabla o apartado | Tabla 3.1: Parámetros Técnicos Estándar |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Estandarizar velocidad a 25 mm/s, ganancia a 10 mm/mV y filtros entre 0.05 y 150 Hz. Identificar y descartar artefactualidad por temblor o interferencia de red. |
| Resultado o nivel asociado | Trazado apto para diagnóstico / Alerta de artefacto excesivo. |
| Acción indicada por la fuente | Aplicar filtro digital de muesca (Notch 50 Hz) y pasa-banda; rechazar señal si SNR \< 15 dB. |
| Excepciones informadas | Pacientes con marcapasos (requiere filtro de alta frecuencia ampliado a 250 Hz). |
| Datos obligatorios para aplicarla | Señal digitalizada (frecuencia de muestreo $\ge 500\text{ Hz}$). |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Coincidencia total en el ancho de banda diagnóstico básico (0.05 \- 150 Hz). |
| Decisión de la autoridad responsable | Adoptar filtrado FIR digital automático en el microcontrolador ESP32. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `signal_filter.py` \-\> `apply_bandpass_notch_filter()` |
| Grupo responsable | Grupo 1 \- Procesamiento Digital de Señales |
| Datos de entrada | Array de datos crudos ADC (ESP32) |
| Resultado esperado | Array de datos filtrados \+ Indicador SNR |
| Pruebas automáticas asociadas | `test_signal_quality_filtering.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 3: Cálculo de Frecuencia Cardíaca (FC)

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-003 |
| Nombre breve | Cálculo de Frecuencia Cardíaca (FC) |
| Módulo relacionado | Módulo de Análisis Ritmo y Frecuencia |
| Variable utilizada | Frecuencia Cardíaca (FC) e Intervalos R-R |
| Unidad de medida | LPM (Latidos por minuto) / ms |
| Población de aplicación | Pacientes adultos en triaje |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | OMS / Ministerio de Salud de la Nación |
| Nombre completo del documento | Guía Práctica Clínica de Triaje de Urgencias y Emergencias |
| Versión o edición | 2025 |
| Fecha de publicación | 2025 |
| URL oficial | [https\://www\.who.int/es](https://www.who.int/es) |
| Página | Pág. 42 |
| Tabla o apartado | Tabla de Frecuencia Cardíaca y Signos Vitales |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Ritmo regular: $300 / \text{N° cuadros grandes RR}$ (o $1500 / \text{cuadros pequeños}$). Ritmo irregular: Contar QRS en $6\text{ seg} \times 10$ (o $10\text{ seg} \times 6$). |
| Resultado o nivel asociado | Valor numérico de FC (LPM) y categoría (Normal, Taquicardia, Bradicardia). |
| Acción indicada por la fuente | Clasificar nivel de urgencia según rangos de FC ($< 50\text{ LPM}$ o $> 120\text{ LPM}$ en reposo activan alerta). |
| Excepciones informadas | Atletas de alto rendimiento (bradicardia fisiológica), niños. |
| Datos obligatorios para aplicarla | Detección precisa de picos R (algoritmo Pan-Tompkins). |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Estándar matemático universalmente aceptado. |
| Decisión de la autoridad responsable | Implementar algoritmo híbrido según la regularidad del ritmo. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `metrics_calculator.py` \-\> `calculate_heart_rate()` |
| Grupo responsable | Grupo 2 \- Algoritmos Clínicos |
| Datos de entrada | Vector de marcas temporales de Picos R |
| Resultado esperado | `int hr_bpm`, `string hr_category` |
| Pruebas automáticas asociadas | `test_hr_calculation_algorithms.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 4: Evaluación de Regularidad

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-004 |
| Nombre breve | Evaluación de Regularidad |
| Módulo relacionado | Módulo de Clasificación de Arritmias |
| Variable utilizada | Variabilidad de Intervalos R-R ($R{R}_{i}$) |
| Unidad de medida | ms / Desviación Estándar |
| Población de aplicación | Población general |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Sociedad Argentina de Cardiología (SAC) |
| Nombre completo del documento | Consenso de Arritmias Cardíacas y Electrocardiografía |
| Versión o edición | Vol. 91, N° 4 |
| Fecha de publicación | 2023 |
| URL oficial | [https\://www\.sac.org.ar](https://www.sac.org.ar) |
| Página | Págs. 112-115 |
| Tabla o apartado | Sección 4: Clasificación del Ritmo |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Analizar variabilidad de intervalos R-R inter-latido. Clasificar en ritmo sinusal regular, arritmia sinusal o ritmos irregulares. |
| Resultado o nivel asociado | Clasificación: Ritmo Sinusal Regular, Arritmia Sinusal o Ritmo Irregular. |
| Acción indicada por la fuente | Si es irregular desordenado, derivar a regla RC-ECG-005 (Detección de FA). |
| Excepciones informadas | Marcapasos con captura fija, extrasístoles frecuentes aisladas. |
| Datos obligatorios para aplicarla | Mínimo 10 segundos continuos de trazado ECG. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Criterios unificados en normativas nacionales e internacionales. |
| Decisión de la autoridad responsable | Aprobado para clasificación primaria en el tótem. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `rhythm_analyzer.py` \-\> `evaluate_regularity()` |
| Grupo responsable | Grupo 2 \- Software de Análisis Clínico |
| Datos de entrada | Lista de intervalos R-R en milisegundos |
| Resultado esperado | Enum `{REGULAR, RESPIRATORY_ARRHYTHMIA, IRREGULAR}` |
| Pruebas automáticas asociadas | `test_rhythm_regularity.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 5: Detección de Fibrilación Auricular (FA)

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-005 |
| Nombre breve | Detección de Fibrilación Auricular (FA) |
| Módulo relacionado | Módulo de Alertas de Urgencia Cardiovascular |
| Variable utilizada | Onda P, Ondas f, Intervalos R-R |
| Unidad de medida | Cualitativo / Métrica de Irregularidad |
| Población de aplicación | Adultos mayores de 18 años |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de la Nación / ESC (European Society of Cardiology) |
| Nombre completo del documento | Guía de Diagnóstico y Manejo de la Fibrilación Auricular |
| Versión o edición | Edición 2024 |
| Fecha de publicación | 2024 |
| URL oficial | [https\://www\.argentina.gob.ar/salud](https://www.argentina.gob.ar/salud) |
| Página | Págs. 22-26 |
| Tabla o apartado | Tabla 2: Criterios ECG de FA |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Criterios clave: Ausencia de onda P clara, presencia de ondas f de fibrilación o línea de base caótica, e intervalos R-R irregularmente irregulares. |
| Resultado o nivel asociado | Sospecha de Fibrilación Auricular (FA) / Alerta Amarilla-Roja de Triaje. |
| Acción indicada por la fuente | Generar alerta prioritaria en pantalla del Tótem y notificar al personal médico del centro. |
| Excepciones informadas | Flutter auricular con conducción variable (requiere análisis diferencial). |
| Datos obligatorios para aplicarla | Trazado DII / V1 de alta definición libre de artefactos. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Definición clínica universal de FA. |
| Decisión de la autoridad responsable | Aprobada como regla prioritaria de detección de arritmia supraventricular. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `afib_detector.py` \-\> `detect_atrial_fibrillation()` |
| Grupo responsable | Grupo 2 \- Módulo de Triaje Inteligente |
| Datos de entrada | Trazado ECG completo (10s) \+ lista de picos P y R |
| Resultado esperado | `Boolean afib_detected`, `float confidence_score` |
| Pruebas automáticas asociadas | `test_afib_detection_physionet.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 6: Medición de Duración QRS

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-006 |
| Nombre breve | Medición de Duración QRS |
| Módulo relacionado | Módulo de Medición de Intervalos y Morfología |
| Variable utilizada | Duración del Complejo QRS |
| Unidad de medida | ms (milisegundos) |
| Población de aplicación | Población general |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de Córdoba / SAC |
| Nombre completo del documento | Manual de Normatización Electrocardiográfica |
| Versión o edición | 2023 |
| Fecha de publicación | 2023 |
| URL oficial | [https\://www\.cba.gov.ar/salud](https://www.cba.gov.ar/salud) |
| Página | Pág. 55 |
| Tabla o apartado | Tabla 5.1: Intervalos Normales y Conducción Ventricular |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Normal: $< 100\text{ ms}$ ($< 0.10\text{ s}$). Retraso de conducción: $100\text{--}119\text{ ms}$. Bloqueo completo de rama (BRD/BRI) o aberrancia: $\ge 120\text{ ms}$ ($\ge 0.12\text{ s}$). |
| Resultado o nivel asociado | Clasificación Conducción Ventricular (Normal / Retraso / Bloqueo Completo). |
| Acción indicada por la fuente | Si $\text{QRS} \ge 120\text{ ms}$, marcar flag "QRS Ancho" para evaluación de bloqueo de rama o ectopia. |
| Excepciones informadas | Síndrome de Wolff-Parkinson-White, ritmo de marcapasos. |
| Datos obligatorios para aplicarla | Detección de puntos $Q_{\text{onset}}$ y $S_{\text{offset}}$. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Coincidencia plena en el umbral de 120 ms para bloqueo completo. |
| Decisión de la autoridad responsable | Adoptar 120 ms como corte estricto para QRS ancho. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `morphology_analyzer.py` \-\> `measure_qrs_duration()` |
| Grupo responsable | Grupo 2 \- Software de Diagnóstico |
| Datos de entrada | Puntos de inflexión del complejo QRS |
| Resultado esperado | `float qrs_ms`, `string qrs_classification` |
| Pruebas automáticas asociadas | `test_qrs_duration_measurement.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 7: Medición de Intervalo PR

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-007 |
| Nombre breve | Medición de Intervalo PR |
| Módulo relacionado | Módulo de Medición de Intervalos y Conducción AV |
| Variable utilizada | Intervalo PR ($P_{\text{onset}}$ a $R_{\text{onset}}$) |
| Unidad de medida | ms (milisegundos) |
| Población de aplicación | Población general |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de la Nación / AHA |
| Nombre completo del documento | Guías de Conducción Auriculoventricular y Electrocardiografía |
| Versión o edición | 2024 |
| Fecha de publicación | 2024 |
| URL oficial | [https\://www\.argentina.gob.ar/salud](https://www.argentina.gob.ar/salud) |
| Página | Págs. 60-63 |
| Tabla o apartado | Tabla de Conducción AV |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Normal: $120\text{--}200\text{ ms}$ ($0.12\text{--}0.20\text{ s}$) en ritmo sinusal. PR corto: $< 120\text{ ms}$ (preexcitación). PR prolongado: $> 200\text{ ms}$ (Bloqueo AV de 1er grado). |
| Resultado o nivel asociado | Diagnóstico de conducción AV (Normal, Preexcitación, BAV de 1er Grado). |
| Acción indicada por la fuente | Si $\text{PR} > 200\text{ ms}$ o $< 120\text{ ms}$, generar notificación preventiva en ficha de triaje. |
| Excepciones informadas | Ritmos no sinusales (FA, Flutter, ritmo nodal). |
| Datos obligatorios para aplicarla | Presencia de onda P clara antecediendo al QRS. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Sin divergencias en los límites de 120 y 200 ms en adultos. |
| Decisión de la autoridad responsable | Aplicar estándar clínico internacional. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `interval_analyzer.py` \-\> `measure_pr_interval()` |
| Grupo responsable | Grupo 2 \- Software de Análisis Clínico |
| Datos de entrada | Onda P onset y QRS onset |
| Resultado esperado | `float pr_ms`, `string av_conduction_status` |
| Pruebas automáticas asociadas | `test_pr_interval_validation.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 8: Intervalo QT y Cálculo de QTc

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-008 |
| Nombre breve | Intervalo QT y Cálculo de QTc |
| Módulo relacionado | Módulo de Riesgo de Repolarización Ventricular |
| Variable utilizada | Intervalo QT y QT Corregido (QTc) |
| Unidad de medida | ms (milisegundos) |
| Población de aplicación | Población general (separado por sexo) |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | OMS / Ministerio de Salud de la Nación / AHA |
| Nombre completo del documento | Consenso de Repolarización Ventricular y Canalopatías |
| Versión o edición | 2023 |
| Fecha de publicación | 2023 |
| URL oficial | [https\://www\.who.int/es](https://www.who.int/es) |
| Página | Págs. 88-92 |
| Tabla o apartado | Criterios de Bazett y Fridericia |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Medición manual/algorítmica desde inicio de QRS hasta fin de onda T. Fórmula Bazett/Fridericia: $QTc=\frac{QT}{\sqrt{RR}}$. Normal: $\le 450\text{ ms}$ (H) / $\le 460\text{ ms}$ (M). Prolongado: $> 470\text{--}500\text{ ms}$. |
| Resultado o nivel asociado | Valor de QTc y nivel de riesgo de arritmias ventriculares (Torsades de Pointes). |
| Acción indicada por la fuente | Si $\text{QTc} > 500\text{ ms}$, emitir Alerta Roja de Riesgo Proarrítmico Crítico. |
| Excepciones informadas | Frecuencias cardíacas extremas ($< 50\text{ LPM}$ o $> 120\text{ LPM}$, donde se prefiere Fridericia). |
| Datos obligatorios para aplicarla | QT medido, Intervalo R-R previo, Sexo del paciente. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | Sí |
| ¿Las fuentes coinciden? | No |
| Diferencias encontradas | Bazett sobrecorrige a FC elevadas; Fridericia es más precisa en taquicardia. |
| Decisión de la autoridad responsable | Utilizar Bazett para FC entre 60 y 100 LPM y Fridericia fuera de ese rango. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `qt_calculator.py` \-\> `calculate_qtc()` |
| Grupo responsable | Grupo 2 \- Módulo de Diagnóstico Automático |
| Datos de entrada | `qt_ms`, `rr_sec`, `patient_gender` |
| Resultado esperado | `float qtc_ms`, `string risk_level` |
| Pruebas automáticas asociadas | `test_qtc_formulas.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA

---

# Regla 9: Evaluación de Segmento ST y Onda T

## 1\. Identificación de la regla

| Campo | Contenido |
| :---- | :---- |
| Identificador de la regla | RC-ECG-009 |
| Nombre breve | Evaluación de Segmento ST y Onda T |
| Módulo relacionado | Módulo de Isquemia y Cardiopatía Aguda |
| Variable utilizada | Desviación del Segmento ST, Polaridad y Amplitud de Onda T |
| Unidad de medida | mV / mm |
| Población de aplicación | Adultos mayores de 18 años |
| Versión de la regla | 1.0 |
| Fecha de incorporación | 26/10/2026 |

## 2\. Fuente oficial

| Campo | Contenido |
| :---- | :---- |
| Organismo responsable | Ministerio de Salud de la Nación / Cuarta Definición Universal del Infarto (ESC/ACC/AHA/WHF) |
| Nombre completo del documento | Guía Práctica Clínica de Síndrome Coronario Agudo en Emergencias |
| Versión o edición | Edición 2024 |
| Fecha de publicación | 2024 |
| URL oficial | [https\://www\.argentina.gob.ar/salud](https://www.argentina.gob.ar/salud) |
| Página | Págs. 10-14 |
| Tabla o apartado | Tabla 1: Criterios Electrocardiográficos de Isquemia y Lesión |
| Fecha de consulta | 26/10/2026 |

## 3\. Contenido de la regla

| Campo | Contenido |
| :---- | :---- |
| Condición documentada | Segmento ST: Medir supra/infradesnivel respecto a la línea isoeléctrica (PR/TP) para isquemia. Onda T: Analizar polaridad, simetría y amplitud (ondas T picudas/invertidas). |
| Resultado o nivel asociado | Sospecha de Isquemia / Lesión Miocárdica Aguda (IAMCEST / IAMSEST). |
| Acción indicada por la fuente | Supra/Infradesnivel $\ge 1\text{ mm}$ ($0.1\text{ mV}$) activa ALERTA ROJA INMEDIATA de Triaje. |
| Excepciones informadas | Repolarización precoz en jóvenes, pericarditis aguda, bloqueo de rama izquierda preexistente. |
| Datos obligatorios para aplicarla | Línea isoeléctrica estable, medición exacta del punto J. |

## 4\. Diferencias entre fuentes

| Pregunta | Respuesta |
| :---- | :---- |
| ¿Se encontraron otras fuentes oficiales? | No |
| ¿Las fuentes coinciden? | Sí |
| Diferencias encontradas | Criterios internacionales unificados según la Cuarta Definición Universal del Infarto. |
| Decisión de la autoridad responsable | Prioridad máxima de implementación en la lógica de triaje. |

## 5\. Revisión profesional

| Campo | Contenido |
| :---- | :---- |
| Nombre del profesional |  |
| Matrícula o identificación profesional |  |
| Institución o función |  |
| Decisión |  |
| Observaciones |  |
| Fecha de revisión |  |
| Firma o constancia |  |

## 6\. Implementación técnica

| Campo | Contenido |
| :---- | :---- |
| Función o archivo donde se implementa | `st_segment_analyzer.py` \-\> `evaluate_st_t_wave()` |
| Grupo responsable | Grupo 2 \- Módulo de Alertas Críticas |
| Datos de entrada | Punto J, Segmento ST, Amplitud Onda T, Isoelectric Baseline |
| Resultado esperado | `float st_deviation_mv`, `string ischemia_risk_flag` |
| Pruebas automáticas asociadas | `test_st_elevation_depression.py` |
| Fecha de implementación | 26/10/2026 |
| Revisión de código | Aprobado |

## 7\. Estado de activación

- [ ] BORRADOR  
- [ ] PENDIENTE DE APROBACIÓN  
- [ ] APROBADA E INACTIVA  
- [x] ACTIVA  
- [ ] RETIRADA