# Fase 3 — Verdad científica RIASEC

## Diagnóstico

La propuesta suministrada exige un inventario RIASEC adaptado y digitalizado, pero no identifica con precisión suficiente la versión exacta del instrumento, el manual de puntuación, la adaptación lingüística empleada ni la evidencia documental que permita afirmar que los 60 ítems actualmente codificados corresponden exactamente a una versión validada.

Por esa razón, el repositorio ya no debe tratar la implementación actual como verdad psicométrica confirmada. La implementación computacional se conserva para pruebas piloto, pero queda marcada como provisional y la recolección definitiva se bloquea hasta completar la verificación científica.

## Controles implementados

- Se añadió un protocolo reproducible para el cálculo y las variables objetivo.
- Los seis puntajes R, I, A, S, E y C se definen como objetivos primarios.
- profile_1, profile_2, profile_3, holland_code y tie_top1 se consideran salidas derivadas.
- La regla computacional de puntuación se identifica como RIASEC_SCORING_PROVISIONAL_V1.
- Se calcula SHA-256 del manifiesto local de los 60 ítems para detectar cualquier cambio futuro.
- Se calcula SHA-256 de la especificación de puntuación.
- La versión del instrumento registra verification_status: unverified, verified o rejected.
- COLLECTION_PHASE=final queda bloqueada mientras verification_status no sea verified.
- El porcentaje mostrado en resultados se etiqueta como porcentaje del máximo posible, nunca como percentil ni probabilidad.

## Qué demuestra el hash y qué no

El hash local demuestra únicamente que el contenido del repositorio no cambió entre ejecuciones. No demuestra que los ítems coincidan con una fuente oficial externa, que la traducción sea autorizada ni que la adaptación posea validez psicométrica.

## Bloqueador científico

Para pasar el instrumento a verified se necesita evidencia documental del instrumento exacto que se utilizará en la tesis. Debe verificarse como mínimo: nombre y versión exactos; fuente; idioma/adaptación; número y orden de ítems; asociación ítem-dimensión; escala de respuesta; regla de puntuación; licencia o permiso de uso; y, si aplica, evidencia de validación profesional mencionada en la propuesta.

No se debe cambiar verification_status a verified por decisión de software ni por coincidencia visual de los ítems.

## Variable objetivo Y

El objetivo primario para el modelado queda definido como el vector de seis puntajes RIASEC. Los códigos ordenados de dos o tres letras pueden derivarse después, preservando empates, pero no sustituyen los seis valores originales como referencia principal.

## Prevención de fuga de información

Las respuestas IP01–IP60 que generan Y permanecen fuera de los predictores del dataset principal. El archivo maestro de auditoría puede conservarlas para trazabilidad, pero no debe usarse como matriz X del experimento principal.

## Criterio de cierre

La Fase 3 solo puede aprobarse cuando: (1) la fuente exacta del instrumento haya sido aportada o verificada con autorización expresa; (2) los 60 ítems, su mapeo y puntuación hayan sido contrastados; (3) la licencia/permiso de uso esté documentada; (4) verification_status pueda pasar justificadamente a verified; (5) migración, seed-catalogs, scientific-status y pytest hayan sido ejecutados sin errores.
