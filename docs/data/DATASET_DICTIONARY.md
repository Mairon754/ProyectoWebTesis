# Diccionario de datos — contrato primario VOC_RIASEC_TEXT_X_V1

| Campo | Rol | Uso en X | Descripción |
|---|---|---:|---|
| participant_code | metadata | No | Código seudónimo aleatorio para trazabilidad interna. |
| collection_phase | metadata | No | Indica si el registro procede de pilot o final. |
| texto_combinado | predictor | Sí | Texto libre T01–T03 concatenado con separador [SEP]. |
| score_r | primary_target | No | Puntaje Realista, escala 0–40. |
| score_i | primary_target | No | Puntaje Investigador, escala 0–40. |
| score_a | primary_target | No | Puntaje Artístico, escala 0–40. |
| score_s | primary_target | No | Puntaje Social, escala 0–40. |
| score_e | primary_target | No | Puntaje Emprendedor, escala 0–40. |
| score_c | primary_target | No | Puntaje Convencional, escala 0–40. |
| profile_1 | derived_target | No | Dimensión de máxima puntuación cuando existe máximo único. |
| profile_2 | derived_target | No | Segunda posición ordenada cuando es inequívoca. |
| profile_3 | derived_target | No | Tercera posición ordenada cuando es inequívoca. |
| holland_code | derived_target | No | Código de tres letras únicamente cuando las tres primeras posiciones son únicas. |
| tie_top1 | derived_target | No | Indica si existe empate exacto en el máximo. |
| split | partition | No | train, validation o test, congelado a nivel participante. |

## Regla de uso

Para el experimento comparativo principal, ninguna columna diferente de `texto_combinado` se considera predictor X bajo este contrato. En particular, `participant_code`, `collection_phase`, las respuestas IP01–IP60 y cualquier variable target quedan excluidas de X.

La estructura puede evolucionar solo mediante una nueva versión del contrato y un nuevo release; no se debe modificar silenciosamente un release ya congelado.
