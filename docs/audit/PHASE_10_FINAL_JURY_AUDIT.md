# Fase 10 — Auditoría final para jurado

## Alcance

Esta auditoría contrasta la propuesta D01 con el estado real del repositorio `desarrollo-AI`. No incorpora fuentes externas ni presume resultados que todavía no existen. El criterio es distinguir entre: **infraestructura implementada**, **evidencia pendiente** y **producto científico todavía no ejecutado**.

## Veredicto ejecutivo

El prototipo técnico de recolección, trazabilidad, privacidad, calidad, versionado y reproducibilidad está suficientemente consolidado para una demostración técnica. Sin embargo, **el proyecto no está listo para presentarse como investigación final concluida ante jurado**.

La causa no es una falla única de software. Existen bloqueadores científicos, metodológicos y de publicación que deben resolverse antes de una defensa final.

### Estado por dimensión

| Dimensión | Estado | Veredicto |
|---|---|---|
| Plataforma de recolección | Verde | Implementada y cubierta por pruebas |
| Consentimiento/elegibilidad | Verde técnico | Flujo implementado; evidencia real de recolección final aún no existe |
| Verdad técnica RIASEC | Verde técnico | Fuente/scoring trazados |
| Validación profesional/local RIASEC | Rojo | Documento escrito pendiente |
| Privacidad y control de acceso | Verde/amarillo | Aplicación reforzada; infraestructura externa no demostrada |
| Control automático de calidad | Verde | Implementado y versionado |
| Dataset científico | Amarillo | Infraestructura lista; dataset final real no existe |
| Reproducibilidad experimental | Verde técnico | Manifiestos y hashes disponibles |
| Modelos comparativos | Rojo | No hay pipelines de entrenamiento/inferencia en el repositorio |
| Evaluación funcional/técnica | Rojo | No existen resultados reales de modelos |
| Estadística comparativa | Rojo | No existe análisis ejecutado y D01 presenta criterios inconsistentes |
| Informe técnico final | Rojo | No existe porque la comparación aún no se ha ejecutado |
| Repositorio público | Rojo | `main` sigue apuntando al primer commit con `.env` y bytecode |
| CI/documentación | Verde en `desarrollo-AI` | GitHub Actions y manual técnico operativos |

## 1. Fortalezas demostrables

### Plataforma y recolección

D01 exige una plataforma web estandarizada con validación, almacenamiento seguro y mecanismos automáticos de control de calidad (D01, p. 31). La rama `desarrollo-AI` implementa el flujo participante, consentimiento/asentimiento, elegibilidad, instrumento, preguntas complementarias, persistencia PostgreSQL, resultados y controles automáticos.

### Ética y menores de edad

D01 exige consentimiento previo y explícito y, para menores, autorización del acudiente (D01, p. 37–38). El prototipo separa consentimiento adulto, autorización del acudiente y asentimiento del menor. La muestra final también queda condicionada a grado 11, institución autorizada y estado científico del instrumento.

### Privacidad

D01 exige encriptación, anonimización previa al procesamiento, control por roles y destrucción segura posterior (D01, p. 37). El repositorio demuestra seudonimización, roles, restricciones de exportación, neutralización de fórmulas, auditoría, recuperación temporal limitada a pestaña y un procedimiento de eliminación sobre la base activa.

No se debe afirmar que el código prueba encriptación física de discos, backups, snapshots o réplicas. Esa evidencia pertenece a infraestructura operativa y todavía no existe en el repositorio.

### Dataset y reproducibilidad

D01 exige CSV/JSON, documentación metodológica, criterios de validación, scripts, configuraciones, métricas y manual técnico (D01, p. 26). El repositorio ya incorpora contrato X/Y, releases versionados, hashes, diccionario, bitácora, control de calidad, manifiestos experimentales, manual técnico y CI.

## 2. Bloqueadores científicos

### 2.1 Validación profesional/local escrita

D01 establece que las etiquetas RIASEC serán verificadas por profesionales en psicología y orientación vocacional mediante pruebas validadas basadas en Holland (D01, p. 26).

El estado correcto continúa siendo:

`instrument_verification_status = unverified`

La revisión profesional positiva informada verbalmente no sustituye el documento escrito. Mientras no se incorpore esa evidencia:

- `COLLECTION_PHASE=final` debe permanecer bloqueada;
- no puede declararse validado localmente el instrumento;
- no debe congelarse un dataset final.

Este es un **bloqueador crítico** para la recolección definitiva.

### 2.2 Dataset final real inexistente

D01 compromete un archivo CSV/JSON anonimizado acompañado de documentación y evidencia de consentimiento (D01, p. 26).

El repositorio contiene la infraestructura para generarlo, pero no contiene datos finales reales, releases finales, ni evidencia de consentimientos de participantes reales. Esto es coherente con el bloqueo actual de recolección, pero significa que ese producto todavía no está cumplido.

### 2.3 Modelos y pipelines aún no implementados

D01 exige un Transformer personalizado y arquitecturas comparativas con pipelines de inferencia, configuraciones estandarizadas, scripts, notebooks y métricas (D01, p. 26; p. 31).

La auditoría del árbol actual no encontró:

- scripts de entrenamiento;
- pipelines de inferencia;
- notebooks `.ipynb`;
- implementación del Transformer personalizado;
- integración operativa de GPT-Neo, GLM-4.6, GPT-o4, Llama 3.1, BERT o RoBERTa.

La Fase 7 prepara **reproducibilidad del experimento**, pero no sustituye la implementación de los modelos.

Este es un **bloqueador crítico para la tesis final**, aunque no bloquea la calidad del prototipo de recolección.

### 2.4 Evaluación comparativa aún no ejecutada

D01 exige Accuracy, F1-score, Recall, latencia y memoria sobre el conjunto de prueba, además de pruebas estadísticas (D01, p. 26; p. 32).

No existe evidencia en el repositorio de:

- resultados reales de modelos;
- matrices de confusión;
- curvas ROC/precision-recall;
- mediciones reales de latencia/memoria;
- ANOVA, Tukey o Kruskal-Wallis ejecutados;
- informe comparativo final.

Por tanto, **no hay evidencia en el corpus/repositorio actual para afirmar cuál arquitectura funciona mejor**.

## 3. Inconsistencias internas de D01 que deben resolverse antes de entrenar

### 3.1 Conjunto de modelos

D01, pp. 3–4 y 26, menciona modelo propio, GPT-Neo, GLM-4.6, GPT-o4 y Llama 3.1. En cambio, D01, pp. 31 y 33, menciona BERT, RoBERTa y GPT-Neo junto con el modelo propio.

Además:

- D01, p. 4 dice “cuatro arquitecturas” pero enumera modelo propio + cuatro modelos nombrados;
- D01, p. 26 dice “tres arquitecturas base” pero enumera cuatro.

No debe iniciarse una comparación final sin una decisión metodológica documentada sobre el conjunto definitivo de arquitecturas.

### 3.2 Pruebas estadísticas

D01, pp. 29 y 32, propone ANOVA, Tukey y Kruskal-Wallis. D01, p. 33, menciona t-test o Mann–Whitney.

Estas rutas no son equivalentes y responden a números de grupos/supuestos diferentes. Antes del análisis final debe existir un plan estadístico único y coherente con la estructura repetida/pareada de las predicciones sobre el mismo conjunto de prueba.

La auditoría no escoge automáticamente una prueba porque D01 no ofrece una decisión única y el experimento real aún no se ha ejecutado.

## 4. Bloqueador de publicación del repositorio

El repositorio es público y la rama por defecto continúa siendo `main`.

La auditoría verificó que:

- `main` apunta todavía al commit inicial `93194032...`;
- ese árbol todavía rastrea `.env`;
- también rastrea múltiples `__pycache__` y `.pyc`;
- `main` no contiene el `.gitignore` ni la documentación actual;
- el historial registra al menos un commit donde existió `.env`;
- `main` y `desarrollo-AI` no están protegidas actualmente.

Las credenciales expuestas fueron rotadas, pero esto **no equivale a sanear el historial**.

Antes de usar el repositorio como evidencia pública final ante jurado se requiere:

1. sanear o reconstruir el historial público sin secretos;
2. mover/actualizar la rama por defecto a una versión limpia y revisada;
3. proteger la rama estable;
4. verificar nuevamente que ningún secreto o bytecode siga accesible en el historial que se publique.

No se recomienda un merge normal de `desarrollo-AI` a `main` antes del saneamiento, porque conservaría el commit histórico con `.env`.

## 5. Estado de seguridad operativa externa

La aplicación implementa controles internos, pero el repositorio no demuestra todavía:

- TLS desplegado;
- cifrado de disco/base/backups;
- política institucional de backups y retención;
- procedimiento real de destrucción de snapshots;
- monitoreo/alertas de infraestructura.

Estos controles deben documentarse si la plataforma pasa a producción con menores de edad.

## 6. Qué sí puede mostrarse hoy a un jurado

Puede demostrarse con evidencia técnica:

- arquitectura web funcional;
- consentimiento y elegibilidad;
- puntuación RIASEC reproducible;
- bloqueo de recolección final;
- privacidad y roles;
- auditoría;
- control automático de calidad;
- dataset versionado;
- particiones reproducibles;
- manifiestos experimentales;
- CI con PostgreSQL y pruebas;
- documentación técnica;
- experiencia accesible/no diagnóstica.

Debe presentarse explícitamente como **infraestructura preparada para la fase experimental**, no como comparación LLM terminada.

## 7. Qué no debe afirmarse todavía

No debe afirmarse que:

- el instrumento está validado profesionalmente en Tumaco;
- existe un dataset final v1.0;
- el sistema ya comparó arquitecturas LLM;
- existe un Transformer personalizado entrenado;
- una arquitectura supera estadísticamente a otra;
- el repositorio público está saneado por completo;
- la eliminación segura incluye backups;
- existe certificación formal de accesibilidad.

## 8. Orden mínimo recomendado antes de defensa final

1. Incorporar la validación profesional/local escrita.
2. Sanear el repositorio público y resolver `main`.
3. Congelar la decisión metodológica sobre modelos y estadística.
4. Ejecutar la recolección definitiva con autorizaciones institucionales.
5. Revisar QC y congelar el dataset final.
6. Implementar Transformer y comparadores aprobados.
7. Registrar todos los experimentos mediante `ExperimentRun`.
8. Medir desempeño funcional y técnico sobre el mismo test set.
9. Ejecutar el plan estadístico aprobado.
10. Elaborar informe comparativo, discusión, limitaciones y conclusiones.
11. Repetir auditoría final de trazabilidad.

## Veredicto de Fase 10

**FASE 10 BLOQUEADA PARA CIERRE FINAL DE TESIS/JURADO.**

La infraestructura del prototipo es sólida y trazable, pero existen bloqueadores críticos fuera de las fases técnicas ya aprobadas: validación profesional escrita, saneamiento del repositorio público, dataset final, implementación de modelos, evaluación comparativa y análisis estadístico.

No se debe cerrar esta fase hasta disponer de evidencia de esos productos.
