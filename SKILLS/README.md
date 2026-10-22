# Skills del curso

Skills para agentes compatibles con el formato [Agent Skills](https://agentskills.io) (OpenCode, Claude Code, Codex, Pi, Gemini CLI, Cursor, Posit Assistant y otros). Son copias de las versiones publicadas en el repositorio [agusnieto77/SKILLS](https://github.com/agusnieto77/SKILLS), que es la fuente de referencia y recibe las actualizaciones.

| Skill | Qué hace | Requisitos |
|---|---|---|
| [`wp-api`](wp-api/) | Trabaja con cualquier sitio WordPress a través de su API REST: descubre `/wp-json/`, exporta entradas, páginas, taxonomías y colecciones de plugins a JSON/NDJSON verificado, y descarga archivos de la biblioteca de medios de cualquier formato (PDF, imágenes, audio, video, documentos, comprimidos) con validación por firma de bytes, manifiesto SHA-256, revisión de `robots.txt` y freno de volumen. Solo lectura pública. | Python 3.10+ con `requests`, o R 4.4+ con `httr2`, `jsonlite` y `digest` |
| [`youtube-api`](youtube-api/) | Recupera datos públicos de un video de YouTube sin cuenta ni clave de API: metadatos, transcripción con marcas de tiempo (subtítulos manuales o automáticos) y comentarios con respuestas, en JSON y CSV, con la cobertura obtenida frente al total declarado. | Python 3.10+ con `requests` |

## Instalación

Copiar la carpeta de la skill al directorio de skills del agente:

| Agente | Proyecto | Todos los proyectos |
|---|---|---|
| Posit Assistant (RStudio) | `.posit/assistant/skills/` | `~/.posit/assistant/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex y otros | `.agents/skills/` | `~/.agents/skills/` |

Después instalar las dependencias desde la carpeta de la skill (`python -m pip install -r assets/requirements.txt`) y abrir una conversación nueva: la skill se carga sola ante un pedido pertinente o se invoca por su nombre. El `README.md` de cada skill explica comandos, salidas y límites.

## Licencia

Las skills de esta carpeta se distribuyen bajo la licencia Apache 2.0 ([LICENSE](LICENSE)). El resto del repositorio del curso mantiene su propia licencia.
