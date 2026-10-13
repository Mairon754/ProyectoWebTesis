# Fase 2 — Ética, consentimiento y elegibilidad de la muestra

## Alcance

Esta fase traduce al software los criterios éticos y poblacionales ya definidos
en la propuesta de investigación. No reemplaza los documentos firmados ni la
autorización institucional: la plataforma registra referencias y bloquea
sesiones que no cumplen las reglas configuradas.

## Reglas implementadas

### 1. Separación piloto / muestra definitiva

La variable de entorno `COLLECTION_PHASE` admite:

- `pilot`: permite pruebas controladas con grado 10 u 11.
- `final`: restringe la muestra principal a grado 11, San Andrés de Tumaco e
  instituciones previamente autorizadas.

La fase se persiste en `assessment_sessions.collection_phase` para impedir que
registros piloto se confundan posteriormente con la muestra definitiva.

### 2. Instituciones autorizadas

`AUTHORIZED_INSTITUTION_CODES` contiene únicamente códigos internos de
instituciones que ya cuentan con autorización formal para participar. La
aplicación no crea ni supone esa autorización; simplemente impide que una
institución no incluida ingrese a la recolección final.

La evidencia documental de cada autorización debe conservarse fuera del
dataset de participantes, dentro del expediente ético/administrativo del
proyecto.

### 3. Participantes menores de 18 años

Para iniciar una sesión se requieren simultáneamente:

- consentimiento previo del acudiente;
- referencia verificable de dicha autorización;
- asentimiento afirmativo del estudiante.

La referencia del acudiente debe ser un código anónimo de 6 a 100 caracteres
formado por letras, números, guion o guion bajo. No se almacenan nombres,
documentos, teléfonos o correos del acudiente en esta tabla.

### 4. Participantes de 18 años o más

Otorgan su propio consentimiento. El sistema rechaza referencias de acudiente
para este grupo con el fin de mantener coherencia y minimización de datos.

### 5. Coherencia de edad

La modalidad elegida en la pantalla de consentimiento se contrasta con la edad
declarada posteriormente. Si no coinciden, la evaluación no se crea y el
participante debe corregir el flujo.

## Límites actuales

- La plataforma registra una referencia, pero no digitaliza la firma del
  acudiente. La autorización firmada debe gestionarse por el mecanismo
  institucional definido por el estudio.
- La lista real de instituciones autorizadas aún debe configurarse por el
  equipo investigador; no debe inventarse.
- El mecanismo formal de retiro posterior de datos se cerrará junto con la
  política de privacidad y gobernanza de datos.
- Las pruebas automatizadas deben ejecutarse contra la base PostgreSQL de
  pruebas antes de aprobar definitivamente la fase.

## Criterio de cierre

La Fase 2 puede aprobarse cuando:

1. `flask db upgrade` aplica la migración de `collection_phase`;
2. `pytest -v` pasa en la base de pruebas;
3. se verifica manualmente un caso menor, uno adulto y un rechazo de grado 10
   con `COLLECTION_PHASE=final`;
4. antes de recolectar la muestra definitiva se configuran únicamente códigos
   de instituciones con autorización documental real.
