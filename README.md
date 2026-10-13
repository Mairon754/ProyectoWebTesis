# Proyecto Web Tesis — Plataforma RIASEC

Plataforma web de apoyo a la investigación de tesis sobre comparación de arquitecturas de inteligencia artificial para clasificación de perfiles vocacionales RIASEC en estudiantes de grado 11 de Tumaco.

> Estado actual: desarrollo metodológico y técnico. La recolección definitiva permanece bloqueada hasta incorporar la validación profesional/local escrita del instrumento.

## Alcance actual

El repositorio implementa:

- flujo de consentimiento/asentimiento y elegibilidad;
- instrumento RIASEC de 60 ítems con trazabilidad O*NET;
- cálculo reproducible de seis puntajes RIASEC;
- preguntas complementarias y texto libre T01–T03;
- módulo privado de investigación con roles;
- control automático e histórico de calidad;
- releases científicos versionados de dataset;
- manifiestos reproducibles de experimentos;
- controles de privacidad, integridad y auditoría;
- suite automatizada con PostgreSQL;
- integración continua mediante GitHub Actions.

El contrato experimental primario vigente es:

`VOC_RIASEC_TEXT_X_V1`

con:

- X primaria: `texto_combinado`;
- Y primaria: seis puntajes RIASEC;
- targets derivados: perfiles ordenados, código Holland y empate superior.

## Requisitos

- Python 3.14
- PostgreSQL
- Git

Las dependencias Python están declaradas en `requirements.txt`.

## Instalación local

### 1. Crear entorno virtual

En Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar dependencias

```cmd
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configurar variables locales

Copiar:

```cmd
copy .env.example .env
```

y reemplazar únicamente en el archivo local los valores de ejemplo.

Nunca se debe versionar `.env`.

Se requieren dos bases separadas:

```text
DATABASE_URL      -> base de desarrollo
TEST_DATABASE_URL -> base exclusiva de pruebas
```

La base de pruebas debe incluir `test` en su nombre y nunca puede ser la misma de desarrollo.

### 4. Aplicar migraciones

```cmd
python -m flask --app run.py db upgrade
python -m flask --app run.py db current
```

### 5. Sembrar y verificar catálogos

```cmd
python -m flask --app run.py seed-catalogs
python -m flask --app run.py scientific-status
```

### 6. Ejecutar pruebas

```cmd
python -m pytest -v
```

### 7. Ejecutar la aplicación

```cmd
python -m flask --app run.py run
```

## Comandos científicos principales

### Control automático de calidad

```cmd
python -m flask --app run.py quality-scan --scope completed
```

### Congelar un release científico

Las proporciones deben definirse metodológicamente antes de ejecutar un release definitivo.

```cmd
python -m flask --app run.py dataset-freeze --version VERSION --collection-phase pilot --train-ratio 0.60 --validation-ratio 0.20 --test-ratio 0.20
```

Los valores anteriores son únicamente un ejemplo de sintaxis.

### Consultar manifiesto de dataset

```cmd
python -m flask --app run.py dataset-manifest --version VERSION
```

### Empaquetar dataset

```cmd
python -m flask --app run.py dataset-package --version VERSION
```

### Estado reproducible del entorno

```cmd
python -m flask --app run.py repro-status
```

### Registrar una ejecución experimental

```cmd
python -m flask --app run.py experiment-register --run-code RUN_001 --dataset-version VERSION_DATASET --model-name MODELO --model-version VERSION_MODELO --run-type evaluation --seed 42 --hyperparameters-json "{}" --conditions-json "{\"split\":\"test\"}"
```

## Experiencia del participante

La interfaz conserva como fortalezas del prototipo:

- navegación por teclado y foco visible;
- enlace para saltar al contenido;
- progreso accesible;
- lectura opcional en voz alta;
- soporte para movimiento reducido y colores forzados;
- modo claro/oscuro;
- guardado automático con recuperación temporal limitada a la pestaña;
- funcionamiento básico mediante formularios aunque JavaScript esté desactivado;
- resultados presentados como **perfil de intereses RIASEC**, no como diagnóstico psicológico.

Detalles y límites: `docs/product/PHASE_9_CONSOLIDATED_STRENGTHS.md`.

## Seguridad y datos

No deben subirse al repositorio:

- archivos `.env`;
- datos crudos o privados;
- exportaciones de investigación;
- pesos de modelos;
- checkpoints;
- bases locales;
- credenciales o tokens.

El comando:

```cmd
python scripts/check_repo_hygiene.py
```

verifica que Git no esté rastreando varias categorías de archivos prohibidos.

El historial antiguo del repositorio puede requerir saneamiento independiente antes de una publicación definitiva; que el árbol actual esté limpio no implica que el historial completo haya sido reescrito.

## Integración continua

El workflow:

`.github/workflows/ci.yml`

ejecuta automáticamente:

1. PostgreSQL 16;
2. instalación de dependencias;
3. creación de base aislada de pruebas;
4. compilación de fuentes Python;
5. control de higiene del repositorio;
6. migraciones;
7. carga/verificación del instrumento;
8. suite completa de pytest.

Detalles adicionales: `docs/ci/CI_AND_VALIDATION.md`.

## Documentación técnica

- `docs/ethics/` — consentimiento, elegibilidad y ética.
- `docs/security/` — privacidad, acceso e integridad.
- `docs/methodology/` — instrumento y metodología del dataset.
- `docs/data/` — diccionario, versionado y control de calidad.
- `docs/reproducibility/` — reproducibilidad experimental.
- `docs/ci/` — integración continua y procedimiento de validación.

## Restricciones vigentes

No debe activarse `COLLECTION_PHASE=final` mientras `instrument_verification_status` permanezca `unverified`.

La revisión profesional/local ha sido informada como positiva, pero su evidencia escrita todavía no está incorporada al repositorio. Por rigor metodológico, esa validación sigue pendiente documentalmente.

## Rama de trabajo

El desarrollo actual se realiza en:

`desarrollo-AI`

La rama `main` debe mantenerse estable hasta completar revisión y consolidación.
