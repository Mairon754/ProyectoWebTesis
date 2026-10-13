# Bitácora de versiones del dataset

## Estado actual

Todavía no existe un release definitivo v1.0 de datos reales. La infraestructura de versionado y congelación se implementó en la Fase 5.

## 2026-10-13 — contrato VOC_RIASEC_TEXT_X_V1

Se define el contrato primario para comparación de arquitecturas:

- X común: `texto_combinado`;
- Y primaria: seis puntajes RIASEC;
- targets derivados conservados para análisis;
- separación determinista a nivel participante;
- proporciones de train/validation/test obligatoriamente explícitas;
- snapshots y hashes SHA-256 por registro y por release;
- diccionario de datos y manifiesto generables;
- release final bloqueado mientras la validación profesional/local del instrumento siga pendiente.

## Regla de versionado

Cada cambio en variables, reglas de limpieza, definición de X/Y, protocolo de split, instrumento o scoring exige una nueva versión del release y debe conservarse en esta bitácora.

No se sustituye silenciosamente un dataset ya utilizado en experimentos.
