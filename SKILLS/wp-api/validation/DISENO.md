# Diseño de la revisión integral

## Objetivo y límites

Una URL y una petición natural bastan para iniciar. El agente descubre el sitio y ejecuta consultas públicas acotadas; pregunta únicamente por intención ambigua, autorización o secretos imprescindibles. Sin sitio propio ni credenciales no se prueban escrituras en terceros.

## Decisión

Conservar una SKILL portable con referencias bajo demanda y extender los clientes a **medios de cualquier formato** y **exportación JSON** de colecciones. No construir un servidor MCP ni un SDK universal: las herramientas HTTP nativas del agente sirven para REST general; scripts deterministas para descubrimiento, archivos y capturas. No mantener tres variantes de instrucciones para tres marcas de agente.

Alternativas descartadas: convertir los CLI en clientes universales de todas las operaciones WordPress duplicaría lógica y superficie de seguridad; limitar la revisión al README dejaría errores reales de descubrimiento y reglas contradictorias.

## Plan por archivos

1. `assets/wp_api.py`, `assets/wp_api.R` y suites: conservar subdirectorios, descubrir índices con rutas bonitas y `rest_route`, reutilizar raíz descubierta y distinguir errores. CLI público de medios multi-formato (`media`/`download`) y exportación (`export`), con registro MIME, firmas de bytes y manifiesto unificado.
2. `SKILL.md`: entrada URL-first, selección progresiva, límites, confirmación y salida verificable.
3. `references/rest-api.md`, `references/autenticacion.md`, `references/operaciones.md`: descubrimiento, permisos, secretos, planificación, recuperación y verificación de cambios. Referencias de descarga/exportación multi-formato y ética, corrigiendo afirmaciones incompatibles.
4. README raíz, README interno y `references/plataformas.md`: instalación nativa, invocación, ejercicios y diagnóstico para estudiantes.
5. `validation/ESCENARIOS.md`, suites existentes y nueva evidencia: pruebas controladas, smoke público y límites explícitos. No equiparar fixtures a instalaciones WordPress reales ni disponibilidad de un ejecutable a validación del agente.

## Criterios

- 404/HTML en una ruta no demuestra ausencia de API.
- Las rutas y métodos anunciados no demuestran permisos del usuario.
- GET público no solicita credenciales; cambios requieren alcance y consentimiento.
- Credenciales nunca en prompts, argumentos, archivos versionados ni informes; no reenvío entre orígenes.
- Escritura con respuesta incierta se reconcilia, no se repite a ciegas.
- Informar evidencia y cobertura parcial, no inventar éxito.
