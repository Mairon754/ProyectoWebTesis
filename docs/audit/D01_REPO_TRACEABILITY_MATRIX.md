# Matriz de trazabilidad D01 ↔ repositorio

| Requisito D01 | Evidencia D01 | Evidencia actual en repositorio | Estado |
|---|---|---|---|
| Plataforma web estructurada | D01, p. 31 | Flask/PostgreSQL, formularios, API, tests | Implementado |
| Consentimiento/asentimiento | D01, p. 37–40 | Flujo adulto/menor, referencia de acudiente | Implementado técnicamente |
| Protección y acceso por roles | D01, p. 37 | Roles viewer/data_manager, auditoría, headers | Implementado en aplicación |
| Cifrado/retención/destrucción | D01, p. 37–40 | Purga DB activa; no evidencia de cifrado/backups | Parcial / operativo pendiente |
| Verificación profesional RIASEC | D01, p. 26 | Estado unverified + bloqueo final | **Bloqueador** |
| Dataset CSV/JSON anonimizado | D01, p. 26, 31 | Generador de releases + CSV/JSON | Infraestructura lista; datos finales pendientes |
| Diccionario/bitácora | D01, p. 34 | DATASET_DICTIONARY + CHANGELOG | Implementado |
| Transformer propio | D01, p. 26, 31 | No encontrado | **Pendiente crítico** |
| Pipelines modelos comparativos | D01, p. 26, 31 | No encontrados | **Pendiente crítico** |
| Hiperparámetros y entorno | D01, p. 31 | ExperimentRun + repro-status | Infraestructura implementada |
| Accuracy/F1/Recall | D01, p. 26, 32 | Soporte de métricas en manifiesto; sin resultados reales | Pendiente ejecución |
| Latencia/memoria | D01, p. 26, 32 | Soporte de métricas; sin resultados reales | Pendiente ejecución |
| ANOVA/Tukey/Kruskal-Wallis | D01, p. 29, 32 | No hay análisis real | Pendiente + decisión metodológica |
| t-test/Mann–Whitney | D01, p. 33 | No hay análisis real | Inconsistencia D01 |
| Informe técnico comparativo | D01, p. 26 | No existe | Pendiente |
| Manual técnico/repositorio | D01, p. 26 | README, TECHNICAL_MANUAL, docs, CI | Implementado en desarrollo-AI |
| Repositorio limpio para publicación | Implícito en medio de verificación | main histórico conserva .env/bytecode | **Bloqueador de publicación** |
| CI/reproducibilidad | D01, p. 16, 26, 31 | GitHub Actions + hashes + manifests | Implementado |
| Experiencia no encasillante | D01, p. 9 | Lenguaje no diagnóstico, intereses RIASEC | Implementado |

## Lectura de la matriz

“Implementado” significa que existe código/documentación verificable. “Infraestructura lista” significa que el mecanismo existe pero el producto real depende de recolección/experimentos aún no realizados. “Bloqueador” significa que la defensa final no debería presentar ese requisito como cumplido.
