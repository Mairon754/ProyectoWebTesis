# Integración continua y validación técnica

## Objetivo

La integración continua reproduce automáticamente las comprobaciones mínimas necesarias para detectar regresiones de código, problemas de migración y contaminación del repositorio.

El workflow está definido en:

`.github/workflows/ci.yml`

## Eventos

Se ejecuta en:

- `push` a `main`;
- `push` a `desarrollo-AI`;
- `pull_request` hacia `main`;
- `pull_request` hacia `desarrollo-AI`;
- ejecución manual mediante `workflow_dispatch`.

## Entorno

El job utiliza:

- Ubuntu;
- Python 3.14;
- PostgreSQL 16;
- una base `riasec_db` para migraciones/catálogos;
- una base separada `riasec_test_db` para pytest.

Las credenciales usadas dentro del workflow son locales y efímeras del servicio PostgreSQL de CI. No corresponden a credenciales reales del proyecto.

## Pasos

1. checkout del repositorio;
2. configuración de Python;
3. instalación de `requirements.txt`;
4. creación explícita de `riasec_test_db`;
5. compilación de fuentes mediante `compileall`;
6. `scripts/check_repo_hygiene.py`;
7. `flask db upgrade`;
8. `flask db current`;
9. `seed-catalogs`;
10. `scientific-status`;
11. `pytest -v`.

## Qué protege

El workflow detecta, entre otros:

- errores de sintaxis/importación;
- migraciones que no aplican desde una base vacía;
- incompatibilidades entre modelos y esquema;
- alteraciones accidentales del instrumento/scoring;
- regresiones de seguridad, privacidad, calidad y reproducibilidad cubiertas por tests;
- archivos privados o binarios prohibidos rastreados por Git.

## Qué NO demuestra

Una ejecución verde de CI no demuestra:

- seguridad completa de infraestructura;
- eliminación física de backups;
- validez psicométrica local;
- corrección estadística de futuros experimentos;
- determinismo de GPU o proveedores externos;
- ausencia absoluta de secretos en todo el historial Git.

El historial antiguo debe tratarse separadamente si se decide sanearlo antes de publicación.

## Regla de trabajo

Antes de integrar cambios hacia `main` se espera:

- CI verde;
- migraciones revisadas;
- pruebas locales relevantes aprobadas;
- documentación de cualquier cambio metodológico;
- ningún dataset o secreto versionado.

## Diagnóstico de fallos

Si falla `Repository hygiene`, ejecutar localmente:

```cmd
python scripts/check_repo_hygiene.py
```

Si falla PostgreSQL/migración:

```cmd
python -m flask --app run.py db upgrade
python -m flask --app run.py db current
```

Si falla la suite:

```cmd
python -m pytest -v
```

Siempre debe comprobarse primero que `TEST_DATABASE_URL` apunta a una base exclusiva de pruebas.
