# Fase 3 — Verdad científica RIASEC

## Resultado de la verificación externa autorizada

El 2026-10-13 se contrastó la implementación local con documentación oficial de O*NET®.

Fuentes oficiales verificadas:

- O*NET Web Services — Short Form Questions (60-question desktop version):
  https://services.onetcenter.org/reference/mpp/ip/ip_questions
- O*NET Interest Profiler Manual — Version 1.0:
  https://www.onetcenter.org/dl_files/IP_Manual.pdf
- O*NET Career Exploration Tools Content License:
  https://www.onetcenter.org/license_tools.html

La documentación oficial confirma que la forma corta contiene 60 preguntas, cinco opciones de respuesta y seis áreas RIASEC. La lista oficial de preguntas fue revisada por O*NET el 2018-05-01.

El contenido local congelado del repositorio fue contrastado con la lista oficial española publicada por O*NET Web Services. El manifiesto verificado conserva el hash SHA-256:

`c30279b792fde80681f96f1c3108ccbedbcb7547dbdee29a90c2d48221433c43`

El mismo hash se almacena como `source_hash_sha256` y `local_content_hash_sha256`; cualquier cambio posterior del texto, orden o dimensión provoca una discrepancia detectable.

## Regla de puntuación

El manual oficial indica que la forma corta computarizada usa cinco opciones codificadas 0–4 y suma diez respuestas por cada dimensión RIASEC, produciendo un rango 0–40.

La interfaz de O*NET Web Services entrega esas mismas cinco respuestas como valores 1–5. Por ello la transformación local:

`response_raw - 1`

es computacionalmente equivalente a la codificación 0–4 del manual antes de sumar por dimensión.

La regla queda versionada como:

`ONET_IP_SHORT_FORM_SCORING_V1`

con un SHA-256 de la especificación para detectar modificaciones futuras.

## Licencia y atribución

Como la tesis integra el instrumento dentro de una plataforma mayor y añade funcionalidad propia, el repositorio documenta el uso bajo la `O*NET Tools Developer License`.

La interfaz muestra atribución a O*NET Career Exploration Tools y al U.S. Department of Labor, Employment and Training Administration (USDOL/ETA), enlaza a la licencia y aclara que USDOL/ETA no ha aprobado, avalado ni probado las modificaciones de esta plataforma.

La licencia exige validar los productos que incorporan contenido de las herramientas. Por ello la verificación de procedencia oficial no sustituye la validación profesional prevista en la propuesta de tesis.

## Estado científico

Se separan dos niveles:

1. `source_verification_status`: la fuente, los 60 ítems, su orden, áreas, escala y regla computacional han sido contrastados con fuentes oficiales O*NET.
2. `instrument_verification_status`: permanece `unverified` hasta documentar la validación profesional prevista en la propuesta para el producto aplicado a estudiantes de grado 11 de Tumaco.

Esta separación evita afirmar que la equivalencia técnica con O*NET sustituye la validación profesional/local.

## Variable objetivo Y

El objetivo primario para el modelado es el vector completo de seis puntajes:

`[score_R, score_I, score_A, score_S, score_E, score_C]`

`profile_1`, `profile_2`, `profile_3`, `holland_code` y `tie_top1` son variables derivadas. No sustituyen los seis valores originales.

La política de empates no fuerza una letra ganadora: si el primer puesto está empatado, no se genera un perfil principal único; si existe un empate que impide ordenar de forma inequívoca los tres primeros puestos, no se genera un código Holland de tres letras.

## Prevención de fuga de información

Las respuestas IP01–IP60 generan la referencia RIASEC Y, por lo que se excluyen de la matriz X del experimento principal. Pueden conservarse únicamente en el dataset maestro de auditoría para trazabilidad y reproducibilidad.

## Bloqueador restante

La propuesta de tesis establece que las etiquetas RIASEC serán verificadas por profesionales en psicología y orientación vocacional mediante pruebas validadas. Esa evidencia local/profesional todavía no está incorporada al repositorio.

Por tanto, `COLLECTION_PHASE=final` continúa bloqueada mientras `instrument_verification_status != verified`.

## Criterio de cierre de Fase 3

La Fase 3 puede cerrarse cuando:

1. la migración vigente esté aplicada;
2. `seed-catalogs` verifique los hashes;
3. `scientific-status` muestre la fuente oficial verificada;
4. la suite `pytest` complete sin fallos;
5. se documente la validación profesional/local prevista en la propuesta;
6. solo después de esa evidencia se evalúe cambiar `instrument_verification_status` a `verified`.
