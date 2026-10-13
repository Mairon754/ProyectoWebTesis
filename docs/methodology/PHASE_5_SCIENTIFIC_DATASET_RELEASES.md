# Fase 5 — Dataset científico versionado

## Objetivo

La propuesta exige construir un dataset especializado y anonimizado, integrarlo en formato tabular, aplicar limpieza/codificación, validar integridad, balance y calidad, y conservar un conjunto de prueba separado. También compromete un dataset anonimizado v1.0 con diccionario de datos y bitácora de versiones.

Esta fase convierte esos requisitos en un contrato reproducible de datos. No entrena modelos ni altera artificialmente la distribución observada.

## Contrato experimental primario

Versión:

`VOC_RIASEC_TEXT_X_V1`

Para la comparación principal entre arquitecturas se fija una entrada común:

- **X primaria:** `texto_combinado`, construido a partir de T01–T03 y separado mediante `[SEP]`.
- **Y primaria:** los seis puntajes `score_r, score_i, score_a, score_s, score_e, score_c`.
- **Y derivada:** `profile_1, profile_2, profile_3, holland_code, tie_top1`.
- **Metadatos no predictivos del paquete:** `record_id` y `collection_phase`. El `participant_code` fuente se conserva únicamente en la tabla interna de membresía y no se exporta en el release.

Las respuestas IP01–IP60, los puntajes RIASEC y los metadatos de participante no forman parte de X. Esto evita fuga de información y obliga a que las arquitecturas comparadas reciban la misma evidencia semántica.

## Elegibilidad

Un registro solo puede entrar a un release cuando:

1. la evaluación está finalizada;
2. existe resultado RIASEC materializado;
3. el control de calidad está en `valid`;
4. `included_ml = true`;
5. existe texto abierto utilizable;
6. el participante aparece una sola vez en el release.

Si aparecen varias sesiones elegibles del mismo participante, la congelación se detiene. El software no decide arbitrariamente cuál conservar.

Para un release `final`, además:

- debe provenir de `collection_phase=final`;
- debe corresponder a grado 11;
- el instrumento debe poseer `verification_status=verified`.

Mientras la validación profesional/local de la Fase 3 siga pendiente, la creación del release definitivo permanece bloqueada.

## Separación train / validation / test

La propuesta exige un conjunto de prueba separado, pero no fija proporciones numéricas. Por ello el software **no inventa** una división predeterminada.

El comando de congelación obliga a proporcionar explícitamente:

- `--train-ratio`
- `--validation-ratio`
- `--test-ratio`

Las tres proporciones deben sumar exactamente 1.

La asignación se realiza a nivel de participante con el protocolo:

`PARTICIPANT_HASH_ORDER_V1`

Los participantes se ordenan de manera determinista mediante SHA-256 usando la versión del release y su código seudónimo. Después se asignan bloques de train, validation y test. Un mismo participante nunca puede quedar en más de una partición.

La congelación se rechaza si alguna partición quedaría vacía.

## Release inmutable

Cada release persiste:

- versión;
- fase de recolección;
- contrato X/Y;
- protocolo de targets;
- protocolo de partición;
- proporciones;
- versión/hash del instrumento;
- hash del scoring;
- hash del esquema;
- hash global del release;
- número de registros;
- snapshot JSON de cada registro;
- split y hash SHA-256 individual por registro.

Los snapshots no dependen de las tablas vivas del participante. Cada archivo exportado usa un `record_id` específico del release y no expone el `participant_code` de la base operativa. La tabla interna de membresía conserva la vinculación necesaria para auditoría mientras exista la base controlada.

## Balance

El manifiesto reporta la distribución observada de `profile_1` y los conteos por split.

No se aplica sobremuestreo, submuestreo ni generación sintética al crear el release. La propuesta exige validar el balance, pero no establece un umbral numérico aceptable; por tanto, **no hay evidencia en el corpus adjunto para imponer automáticamente un porcentaje mínimo/máximo por clase**.

La decisión sobre tratamiento de desbalance debe quedar documentada posteriormente y aplicarse únicamente al conjunto de entrenamiento, nunca al conjunto de prueba.

## Diccionario de datos

El servicio genera un diccionario estructurado que identifica el rol de cada columna como:

- metadata;
- predictor;
- primary_target;
- derived_target;
- partition.

El predictor autorizado del experimento principal queda marcado explícitamente para prevenir inclusión accidental de targets o identificadores.

## Comandos

### Congelar release

Ejemplo para un release piloto:

```powershell
python -m flask --app run.py dataset-freeze --version RIASEC_PILOT_V1 --collection-phase pilot --train-ratio 0.70 --validation-ratio 0.15 --test-ratio 0.15
```

Las proporciones anteriores son solo un ejemplo operativo del comando, **no una proporción aprobada por la propuesta**. Para el release definitivo deberán fijarse y justificarse antes de ejecutarlo.

### Consultar manifiesto

```powershell
python -m flask --app run.py dataset-manifest --version RIASEC_PILOT_V1
```

### Generar paquete local

```powershell
python -m flask --app run.py dataset-package --version RIASEC_PILOT_V1
```

El paquete se crea en `exports/dataset_releases/<version>/`, directorio excluido de Git, e incluye:

- `manifest.json`;
- `data_dictionary.json`;
- `all.csv` y `all.json`;
- `train.csv` y `train.json`;
- `validation.csv` y `validation.json`;
- `test.csv` y `test.json`.

## Bloqueadores para el dataset definitivo

La infraestructura queda implementada, pero no debe declararse todavía que existe el “dataset definitivo v1.0”.

Faltan:

1. documento de validación profesional/local del instrumento;
2. activación justificada de `instrument_verification_status=verified`;
3. recolección real bajo `COLLECTION_PHASE=final`;
4. revisión de calidad de los registros;
5. definición metodológica explícita de las proporciones de split;
6. congelación efectiva del release final;
7. revisión de balance/distribuciones observadas sobre datos reales.

Hasta entonces pueden congelarse releases piloto únicamente para verificar el pipeline.
