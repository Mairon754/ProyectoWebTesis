# Fase 7 — Reproducibilidad experimental y seguridad del investigador

## Fundamento

La propuesta exige documentar hiperparámetros, datasets de entrenamiento y validación y resultados parciales; estandarizar las condiciones de entrenamiento y las métricas; ejecutar todos los modelos sobre el conjunto de prueba; registrar métricas funcionales y técnicas; y sostener una evaluación reproducible. También señala que documentar versiones de datos y modelos garantiza reproducibilidad.

Esta fase implementa la infraestructura de trazabilidad previa a los experimentos. No entrena modelos ni inventa hiperparámetros que todavía no hayan sido aprobados.

## Protocolo de ejecución

Versión:

`EXPERIMENT_RUN_MANIFEST_V1`

Cada ejecución queda ligada obligatoriamente a un `DatasetRelease` congelado de la Fase 5.

El registro conserva:

- `run_code`;
- versión y hash SHA-256 del dataset;
- nombre y versión exacta del modelo;
- tipo de ejecución: `training`, `inference` o `evaluation`;
- semilla, cuando aplique;
- hiperparámetros estructurados;
- condiciones controladas de ejecución;
- versión de Python;
- sistema operativo, arquitectura, procesador y número de CPU visibles;
- snapshot de versiones de paquetes instalados;
- hash del snapshot de paquetes;
- hash de `requirements.txt`;
- commit Git y rama;
- indicador `git_dirty`;
- hash SHA-256 del manifiesto completo;
- estado `registered`, `completed` o `failed`;
- métricas o motivo de fallo al cerrar la ejecución.

## Secretos y credenciales

El servicio nunca serializa `os.environ`.

El entorno registrado se construye mediante una lista explícita de datos técnicos seguros. Las claves JSON cuyo nombre indique contraseña, secreto, token, credencial, API key, DATABASE_URL o private key son rechazadas antes de persistir un manifiesto.

Esto permite documentar, por ejemplo:

```json
{
  "temperature": 0,
  "max_tokens": 500
}
```

pero impide registrar accidentalmente:

```json
{
  "api_token": "..."
}
```

Las credenciales reales deben continuar únicamente en variables de entorno o gestores de secretos externos.

## Versiones instaladas y requirements

El archivo `requirements.txt` usa rangos de compatibilidad, por lo que por sí solo no congela el entorno exacto. Para cada ejecución se captura además el snapshot exacto de paquetes instalados y su hash SHA-256.

Así se conserva tanto:

1. la especificación declarada del proyecto (`requirements.txt`);
2. el entorno realmente utilizado en una ejecución concreta.

No se genera automáticamente un lock global porque el entorno experimental definitivo todavía no está fijado y puede diferir entre modelos locales, GPU o proveedores API.

## Git y código

Cada ejecución registra:

- commit SHA;
- rama;
- si el árbol de trabajo estaba modificado.

Para experimentos definitivos se recomienda trabajar con `git_dirty=false`. El sistema conserva el indicador en lugar de ocultar que una ejecución ocurrió sobre cambios no confirmados.

## Dataset

Una ejecución no acepta un CSV arbitrario: debe referenciar un `DatasetRelease` persistido.

Por tanto, el manifiesto almacena simultáneamente:

- `dataset_version`;
- `dataset_release_hash_sha256`.

Esto permite probar que varias arquitecturas fueron evaluadas sobre exactamente el mismo release.

## Hiperparámetros y condiciones

No se introducen valores por defecto científicos para épocas, batch size, learning rate, temperatura, top-p u otros parámetros.

Cada experimento debe registrarlos explícitamente cuando correspondan al modelo.

Las condiciones también deben declarar los elementos relevantes a la comparabilidad, por ejemplo hardware/dispositivo, split utilizado, modo de inferencia, precisión numérica o proveedor remoto cuando corresponda.

La Fase 7 registra estas condiciones; la estandarización concreta para cada arquitectura se realizará cuando se implementen los pipelines experimentales.

## Métricas

Al completar una ejecución pueden persistirse métricas estructuradas. El protocolo no fuerza todavía nombres numéricos específicos porque la definición exacta de evaluación multisalida y clasificación RIASEC debe mantenerse coherente con el diseño experimental que se implemente posteriormente.

La propuesta sí exige registrar desempeño funcional y técnico, por lo que las ejecuciones de evaluación finales deberán incluir las métricas acordadas antes del análisis comparativo.

## Seguridad de sesiones investigadoras

Las sesiones del módulo privado ahora incorporan una huella SHA-256 derivada de:

- usuario;
- hash de contraseña configurado;
- rol.

En cada acceso protegido se recalcula esta huella contra la configuración vigente.

Si se rota la contraseña, se elimina la cuenta o cambia el rol, una cookie investigadora antigua deja de ser válida y la sesión se limpia automáticamente.

Las sesiones autenticadas se marcan además como permanentes y quedan sujetas a `PERMANENT_SESSION_LIFETIME`, actualmente ocho horas en la configuración base.

## Artefactos fuera de Git

Se excluyen de Git:

- `artifacts/`;
- `checkpoints/`;
- `models/checkpoints/`;
- `wandb/`;
- `mlruns/`;
- pesos `*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`;
- checkpoints temporales de notebooks.

Esto reduce el riesgo de publicar pesos, salidas experimentales grandes o artefactos que puedan incorporar información sensible.

## Comandos

### Estado reproducible

```powershell
python -m flask --app run.py repro-status
```

Muestra commit, estado dirty, hash de requirements y entorno instalado sin imprimir variables de entorno.

### Registrar ejecución

```powershell
python -m flask --app run.py experiment-register --run-code RUN_001 --dataset-version DATASET_V1 --model-name MODELO --model-version VERSION --run-type evaluation --seed 42 --hyperparameters-json "{}" --conditions-json "{\"split\":\"test\"}"
```

### Completar

```powershell
python -m flask --app run.py experiment-complete --run-code RUN_001 --metrics-json "{\"accuracy\":0.80}"
```

### Registrar fallo

```powershell
python -m flask --app run.py experiment-fail --run-code RUN_001 --reason "Descripción no sensible"
```

### Consultar manifiesto

```powershell
python -m flask --app run.py experiment-manifest --run-code RUN_001
```

## Límites

Esta fase no demuestra todavía reproducibilidad numérica entre GPU, librerías o proveedores remotos. Tampoco garantiza determinismo de modelos externos que no expongan semillas o versiones estables.

Lo que sí garantiza es que esas diferencias queden documentadas en el manifiesto cuando se ejecuten los experimentos.

## Criterio de cierre técnico

La Fase 7 puede aprobarse técnicamente cuando:

1. la migración de `ExperimentRun` esté aplicada;
2. la suite completa de pruebas pase;
3. un manifiesto registre release, modelo, semilla, entorno y código;
4. una variable de entorno secreta no aparezca en el manifiesto;
5. claves sensibles sean rechazadas;
6. una ejecución no pueda cerrarse dos veces;
7. una sesión investigadora se invalide después de rotar credenciales.

La validación profesional/local de Fase 3 continúa pendiente y sigue bloqueando la recolección definitiva.
