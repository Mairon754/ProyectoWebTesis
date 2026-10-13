# Manual técnico del prototipo

## Propósito

Este documento funciona como índice técnico de la plataforma de investigación. Describe dónde se encuentra la evidencia de cada control implementado y evita depender únicamente del código fuente para reconstruir el proceso.

## Arquitectura funcional

La aplicación Flask organiza el flujo en cinco áreas principales:

1. **Participante:** consentimiento, demografía, instrumento, preguntas complementarias y resultados.
2. **Investigación:** panel privado, filtros, exportaciones y revisión humana de calidad.
3. **Calidad:** control automático versionado y detección de resultados desactualizados.
4. **Dataset científico:** releases congelados, particiones reproducibles, manifiestos y hashes.
5. **Experimentos:** registro de dataset, modelo, semilla, hiperparámetros, entorno, código y métricas.

PostgreSQL almacena los datos operativos y las bitácoras.

## Trazabilidad metodológica

### Instrumento

Consultar:

- `docs/methodology/PHASE_3_RIASEC_SCIENTIFIC_TRUTH.md`
- `docs/methodology/PHASE_3_DEFERRED_PROFESSIONAL_VALIDATION.md`

### Ética y muestra

Consultar:

- `docs/ethics/PHASE_2_ETHICS_AND_ELIGIBILITY.md`

### Privacidad y acceso

Consultar:

- `docs/security/PHASE_4_INTEGRITY_PRIVACY_ACCESS.md`

### Dataset

Consultar:

- `docs/methodology/PHASE_5_SCIENTIFIC_DATASET_RELEASES.md`
- `docs/data/DATASET_DICTIONARY.md`
- `docs/data/DATASET_CHANGELOG.md`

### Control de calidad

Consultar:

- `docs/data/PHASE_6_AUTOMATIC_QUALITY_CONTROL.md`

### Reproducibilidad

Consultar:

- `docs/reproducibility/PHASE_7_REPRODUCIBILITY_AND_RESEARCH_SECURITY.md`

### Integración continua

Consultar:

- `docs/ci/CI_AND_VALIDATION.md`

## Estados científicos importantes

La fuente O*NET, el contenido local y la regla de scoring están técnicamente trazados. Sin embargo, la validación profesional/local escrita permanece pendiente.

Por ello:

`instrument_verification_status = unverified`

sigue siendo el estado correcto hasta incorporar el documento profesional.

## Recolección definitiva

No debe iniciarse recolección definitiva hasta cumplir simultáneamente:

- autorización institucional real;
- códigos institucionales autorizados configurados;
- validación profesional/local documentada;
- instrumento marcado justificadamente como `verified`;
- `COLLECTION_PHASE=final`;
- migraciones y tests vigentes.

## Datos y experimentación

El contrato principal actual es:

`VOC_RIASEC_TEXT_X_V1`

La X principal del experimento comparativo es `texto_combinado`. Los seis scores RIASEC constituyen la referencia Y primaria.

Un experimento reproducible debe referenciar un `DatasetRelease` congelado y registrarse mediante `ExperimentRun`.

## Control de cambios

Los cambios de:

- instrumento;
- scoring;
- definición de X/Y;
- reglas de calidad;
- protocolo de split;
- dataset;
- hiperparámetros experimentales;

deben quedar versionados y documentados. No se deben sobrescribir silenciosamente protocolos ya utilizados en resultados de tesis.

## Estado del historial Git

El árbol actual impide rastrear `.env`, datasets privados, exportaciones, pesos y artefactos. Esto no equivale a afirmar que el historial público anterior esté saneado.

El saneamiento histórico continúa siendo una actividad separada previa a una eventual publicación definitiva.
