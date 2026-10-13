# Fase 9 — Consolidación de fortalezas del prototipo

## Objetivo

Esta fase consolida capacidades ya existentes de la plataforma sin modificar el protocolo científico, el scoring, el contrato X/Y ni los criterios de elegibilidad. El propósito es reducir ambigüedades de uso, preservar accesibilidad y evitar que futuras modificaciones degraden fortalezas construidas en fases anteriores.

## Alcance científico del resultado

La interfaz pública utiliza ahora de forma consistente la expresión **perfil de intereses RIASEC** y evita presentar el resultado como diagnóstico psicológico o como decisión vocacional definitiva.

La vista de resultados recuerda expresamente que:

- el puntaje describe intereses reportados;
- no mide por sí solo aptitudes o rendimiento académico;
- no determina qué carrera debe elegir el estudiante;
- los porcentajes mostrados corresponden al máximo posible de la escala y no son percentiles ni probabilidades.

Esto mantiene la función orientadora como apoyo a la reflexión y no como mecanismo de encasillamiento.

## Privacidad comunicada con precisión

La página de bienvenida utiliza **código seudónimo** en lugar de afirmar anonimato absoluto.

Esta precisión es coherente con la arquitectura real:

- la base operativa conserva un código de participante para trazabilidad autorizada;
- los releases científicos exportados utilizan identificadores específicos del release;
- el sistema no debe afirmar anonimato absoluto cuando existe una correspondencia interna controlada.

## Accesibilidad y experiencia de uso

Se consolidan las siguientes capacidades existentes:

- enlace global “Saltar al contenido”;
- HTML semántico y formularios tradicionales;
- foco visible para navegación por teclado;
- regiones `aria-live` para mensajes y estados;
- elementos `progress` con etiquetas accesibles;
- controles de lectura en voz alta mediante síntesis del navegador;
- preferencia por voz en español, priorizando `es-CO` cuando está disponible;
- soporte para `prefers-reduced-motion`;
- soporte para `forced-colors`;
- diseño responsivo;
- modo claro/oscuro;
- navegación con botones aunque JavaScript no esté disponible.

La lectura en voz alta es opcional y utiliza síntesis de voz del navegador. No solicita acceso al micrófono.

## Mejora progresiva

La etapa O*NET mantiene un formulario HTML funcional como mecanismo base.

Cuando JavaScript está disponible se agregan:

- guardado automático;
- recuperación temporal limitada a la pestaña;
- gestos verticales;
- transiciones;
- lector de voz;
- feedback dinámico.

Si JavaScript está desactivado, la plataforma muestra una nota explícita indicando que la evaluación puede continuar con los botones tradicionales, aunque dichas mejoras no estarán disponibles.

## Recuperación temporal

La copia temporal del cuestionario utiliza `sessionStorage`, no `localStorage`.

Por ello el estado de recuperación:

- se limita a la pestaña actual;
- no constituye la persistencia oficial;
- no reemplaza PostgreSQL;
- no se conserva deliberadamente como almacenamiento permanente del participante.

## Regresiones protegidas por pruebas

La Fase 9 incorpora pruebas estáticas que verifican:

1. lenguaje seudónimo y no diagnóstico;
2. presencia de progreso accesible y mejora progresiva;
3. foco visible, reducción de movimiento y colores forzados;
4. recuperación con `sessionStorage`;
5. síntesis de voz sin captura de micrófono.

Estas pruebas no sustituyen pruebas de usabilidad con participantes reales, lectores de pantalla ni auditorías formales de WCAG. Su función es impedir que controles ya existentes desaparezcan accidentalmente durante cambios futuros.

## Límites

Esta fase no afirma cumplimiento certificado de WCAG ni demuestra accesibilidad total en todos los dispositivos y tecnologías de asistencia.

Tampoco incorpora recomendaciones automáticas de carreras específicas como resultado principal. El resultado permanece centrado en intereses RIASEC y en ámbitos generales de exploración.

La validación profesional/local escrita del instrumento continúa pendiente y la recolección definitiva debe permanecer bloqueada mientras `instrument_verification_status=unverified`.

## Criterio de cierre técnico

La fase puede aprobarse cuando:

1. la rama local coincida con el HEAD remoto;
2. las nuevas pruebas de experiencia pasen;
3. la suite completa pase;
4. GitHub Actions del HEAD termine en `success`;
5. no se haya modificado scoring, instrumento, contrato X/Y ni migraciones científicas.
