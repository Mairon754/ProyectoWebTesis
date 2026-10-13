# Fase 4 — Integridad, privacidad y control de acceso

## Fundamento

La propuesta exige anonimización previa al procesamiento, control de acceso por roles, acceso restringido, codificación de identificadores y eliminación de datos cuando ya no sean necesarios. Esta fase traduce esos requisitos a controles verificables del prototipo sin afirmar capacidades de infraestructura que no estén demostradas.

## Controles implementados

### Propiedad de la evaluación

Conocer el UUID de una sesión ya no concede acceso. El flujo web vincula la evaluación a la sesión Flask firmada del navegador. La API puede utilizar además un token de capacidad HMAC enviado en la cabecera `X-Assessment-Token`. El token nunca se incluye en URLs.

Las rutas `/assessment/...`, `/results/...` y los endpoints API que consultan o modifican una evaluación verifican posesión antes de acceder a los datos.

La API pública ya no acepta que el cliente elija `participant_code` ni una versión arbitraria del instrumento. El código participante se genera aleatoriamente en el servidor y el instrumento queda fijado por la configuración del proyecto.

### Recuperación temporal en navegador

El autosave oficial continúa en PostgreSQL. La recuperación offline del navegador utiliza `sessionStorage`, no `localStorage`, de modo que la copia temporal queda limitada a la pestaña/sesión del navegador en lugar de persistir indefinidamente en un equipo compartido.

### Acceso investigador por roles

Se definen dos roles:

- `viewer`: consulta el panel y exportaciones de menor sensibilidad.
- `data_manager`: además puede modificar decisiones de calidad y exportar los datasets `master` y `quality`.

Los roles se configuran mediante `RESEARCHER_1_ROLE` y `RESEARCHER_2_ROLE`. Producción rechaza valores distintos de `viewer` y `data_manager`.

### Auditoría de acciones sensibles

Se añadió `research_audit_events`. Se registran al menos inicio/cierre de sesión, exportaciones de dataset y cambios de control de calidad. Las actualizaciones de calidad se guardan en la misma transacción que su evento de auditoría.

### Minimización de identificadores

Los datasets principales `ml`, `transformer` y `results` ya no exportan el UUID interno `session_id`. Conservan `participant_code` como identificador codificado para permitir trazabilidad científica. Los identificadores internos y las respuestas IP01–IP60 permanecen en productos de auditoría restringidos.

### Integridad de exportaciones

Las exportaciones CSV/XLSX neutralizan cadenas iniciadas por `=`, `+`, `-` o `@` para impedir que respuestas textuales sean interpretadas como fórmulas por una hoja de cálculo.

### Eliminación controlada

Se añadió el comando administrativo:

`flask privacy-purge-participant --participant-code CODIGO --confirm CODIGO`

El comando elimina de la base activa el participante y registros asociados mediante las relaciones de cascada. La confirmación duplicada reduce borrados accidentales.

Este comando NO demuestra borrado físico de backups, snapshots, réplicas o almacenamiento administrado fuera de PostgreSQL. La destrucción de esos soportes debe cubrirse mediante el procedimiento institucional de retención y cierre del proyecto.

## Límites que permanecen

El repositorio no demuestra por sí mismo cifrado físico de discos/backups ni políticas del proveedor de hosting. Tampoco debe interpretarse el borrado SQL como sanitización criptográfica de almacenamiento. Esos controles requieren evidencia del entorno de despliegue.

La validación profesional local de la Fase 3 sigue diferida y `COLLECTION_PHASE=final` permanece bloqueada mientras el instrumento no cambie justificadamente a `verified`.

## Validación requerida

Antes de aprobar la Fase 4 se debe:

1. aplicar la migración `e5f7a9b2c4d6`;
2. confirmar `db current` en esa revisión;
3. ejecutar la suite completa de pytest;
4. comprobar que un cliente sin cookie/token recibe HTTP 403 al usar un UUID ajeno;
5. comprobar que el token `X-Assessment-Token` permite al cliente legítimo recuperar su evaluación;
6. comprobar que un `viewer` no puede exportar `master`/`quality` ni modificar calidad;
7. revisar el procedimiento institucional de backups antes de afirmar eliminación segura completa.
