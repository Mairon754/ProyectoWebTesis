# Fase 6 — Control automático de calidad de datos

## Fundamento

La propuesta exige verificar la completitud y consistencia de los datos recolectados mediante mecanismos automáticos y, posteriormente, validar integridad, balance y calidad del dataset. También plantea que la plataforma incorpore validaciones automáticas y filtros de calidad antes de utilizar los datos en investigación.

Esta fase implementa un protocolo automático reproducible sin sustituir la revisión humana.

## Protocolo

Versión:

`DATA_QC_V1_STRUCTURAL_COMPLETENESS`

El protocolo se ejecuta automáticamente al finalizar una evaluación. Para sesiones históricas puede ejecutarse mediante CLI.

Cada ejecución guarda:

- versión del protocolo;
- SHA-256 del estado de entrada evaluado;
- estado `passed` o `blocked`;
- número de bloqueadores;
- número de advertencias;
- detalle de cada regla;
- observaciones;
- fecha de ejecución.

Se conserva historial de ejecuciones. Si el contenido de una sesión cambia después de un control, el resultado previo pasa a considerarse `stale` y no sirve para habilitar inclusión en ML.

## Reglas bloqueantes

El control verifica de manera determinista:

1. sesión finalizada;
2. exactamente 60 respuestas O*NET únicas;
3. valores O*NET entre 1 y 5;
4. coherencia `response_score = response_raw - 1`;
5. tiempos registrados no negativos;
6. exactamente 12 respuestas G01-G12 únicas;
7. valores G01-G12 entre 1 y 5;
8. al menos una materia seleccionada;
9. al menos una actividad seleccionada;
10. presencia no vacía de T01 y T02;
11. consistencia entre texto abierto y `word_count`;
12. resultado RIASEC materializado;
13. puntajes RIASEC dentro del rango 0–40;
14. hashes científicos del instrumento y scoring presentes.

Para registros `collection_phase=final` se comprueba además:

- grado 11;
- `instrument_verification_status=verified`.

## Advertencias

T03 permanece opcional. Su ausencia genera una advertencia, no una exclusión.

La ausencia de metadatos de tiempo de respuesta también puede registrarse como advertencia, pero no se utiliza un umbral de velocidad para excluir registros.

## Criterios que deliberadamente NO se inventan

El corpus adjunto no establece valores numéricos para:

- tiempo mínimo o máximo razonable por pregunta;
- longitud mínima de respuestas abiertas;
- porcentaje máximo de respuestas iguales;
- umbral de cambios de respuesta;
- punto de corte de outliers;
- porcentaje aceptable de balance entre perfiles.

Por ello, el protocolo no excluye automáticamente por esos criterios. Si posteriormente se aprueban metodológicamente, deberán incorporarse mediante una nueva versión del protocolo, no modificando silenciosamente `DATA_QC_V1_STRUCTURAL_COMPLETENESS`.

## Relación con la revisión humana

El control automático y la decisión humana son capas separadas.

Para que `included_ml=true` sea aceptado se requiere:

1. sesión finalizada;
2. control automático vigente con estado `passed`;
3. revisión humana con `quality_status=valid`;
4. versión de dataset indicada.

Un control automático aprobado no marca por sí mismo una sesión como válida para entrenamiento.

## Estado stale

Cada ejecución calcula un hash SHA-256 del contenido evaluado. Si después se modifica una respuesta o metadato estructural relevante, incluido `collection_phase`, el hash actual deja de coincidir con el de la última ejecución.

En ese caso:

`passed → stale`

y la sesión debe volver a someterse al control automático antes de entrar al dataset.

## Ejecución histórica

Para revisar sesiones completadas existentes:

```powershell
python -m flask --app run.py quality-scan --scope completed
```

Para auditar todas las sesiones, incluidas incompletas:

```powershell
python -m flask --app run.py quality-scan --scope all
```

El segundo comando puede producir bloqueos esperables en sesiones todavía en progreso.

## Panel investigador

El panel privado muestra conteos de:

- QC automático aprobado;
- QC automático bloqueado;
- QC no ejecutado o desactualizado.

El dataset de calidad también incorpora el protocolo, estado, bloqueadores, advertencias y si el resultado vigente está aprobado.

## Migración

La tabla histórica se crea mediante:

`a7b9c1d3e5f7_quality_add_automatic_checks.py`

## Criterio de cierre técnico

La Fase 6 puede aprobarse técnicamente cuando:

1. la migración esté aplicada y en `head`;
2. la suite completa de pruebas pase;
3. una sesión completa genere automáticamente un QC `passed`;
4. una sesión incompleta quede `blocked`;
5. una modificación posterior vuelva el control `stale`;
6. `included_ml=true` sea rechazado si el QC no está vigente y aprobado.

La validación profesional/local pendiente de Fase 3 continúa siendo requisito para recolección y release definitivos.


### Interacción con el release final

Si una sesión previamente evaluada como `pilot` se modifica artificialmente a `final`, su control automático anterior pasa a `stale`. Al ejecutar nuevamente el protocolo, `final_instrument_verified` queda como bloqueador mientras la validación profesional/local no esté documentada.

En consecuencia, el servicio de releases puede informar que no existen sesiones elegibles para `collection_phase=final`: esto es esperado porque la capa QC las excluye antes de la congelación. La causa científica queda trazada en `AutomaticQualityCheck.observations_json`.
