# Investigación y auditoría de la SKILL

Consulta de fuentes oficiales: 2026-10-18. Las páginas cambian: las rutas y funciones documentadas no sustituyen la prueba de la versión instalada.

## Fuentes y decisiones

| Fuente primaria | Hallazgo aplicado |
|---|---|
| [Agent Skills: especificación](https://agentskills.io/specification) | `name`/`description` requeridos; nombre igual a carpeta; metadatos string; referencias relativas y carga progresiva. Directorios adicionales permitidos: se conserva `assets/` para no romper rutas existentes. |
| [Codex: skills](https://developers.openai.com/codex/skills) (redirige a [Build skills](https://learn.chatgpt.com/docs/build-skills)) | Descubrimiento `.agents/skills`, invocación `$nombre` o `/skills`, activación implícita por descripción. Instrucciones preferidas frente a scripts salvo comportamiento determinista. |
| [Claude Code: skills](https://code.claude.com/docs/en/skills) | `.claude/skills`, `/nombre`, activación implícita. Extensiones específicas no se vuelven requisitos del núcleo portable. |
| [OpenCode: skills](https://opencode.ai/docs/skills/) | `.opencode/skills`, `.claude/skills`, `.agents/skills`; herramienta nativa `skill`. Slash depende de `metadata["opencode/slash"]`; no se promete como invocación universal. |
| [WordPress: discovery](https://developer.wordpress.org/rest-api/using-the-rest-api/discovery/) | `Link` y HTML anuncian raíz; enlaces simples usan `?rest_route=/`; namespaces/rutas/auth permiten descubrimiento dinámico. |
| [WordPress: authentication](https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/) | Application Passwords sobre HTTPS; cookies requieren nonce apropiado. OAuth/JWT dependen de extensiones. |
| [WordPress: schema](https://developer.wordpress.org/rest-api/extending-the-rest-api/schema/) | Esquema/OPTIONS para campos y argumentos, no prueba de permisos efectivos. |
| [WordPress: posts](https://developer.wordpress.org/rest-api/reference/posts/) | Crear/actualizar mediante POST; estados draft/publish/future/private; borrado condicionado al recurso. No asumir PATCH ni idempotencia universal. |

## Auditoría inicial

| Severidad | Evidencia inicial | Corrección |
|---|---|---|
| Alta | SKILL decía que 404/HTML en `/wp-json/` significa “NO hay API”, mientras su referencia mencionaba alternativas | Descubrimiento con raíz anunciada, subdirectorios y `rest_route`; diagnóstico diferenciado |
| Alta | Regla “solo endpoints públicos GET” seguida de Application Passwords; CLI declaraba no enviar credenciales | Separar cliente PDF público de procedimientos autenticados y cambios del agente |
| Alta | `normalizar_sitio` Python descartaba el path | Preservar instalaciones en subdirectorio y resolver consultas desde raíz descubierta |
| Alta | Ausencia de contrato para publicar, borrar o reconciliar escrituras con respuesta perdida | Confirmación del plan concreto, estado previo/posterior y no reintento ciego |
| Media | README interno decía “todo verificado” con un solo sitio y sin sesiones de agentes | Separar evidencia histórica, ejecución actual, fixtures y recetas no ejecutadas |
| Media | No había README raíz ni instrucciones de instalación/invocación por agente | Guía didáctica y adaptadores documentales sin duplicar lógica |
| Media | Secretos descritos como variables en archivos de entorno sin guía conversacional suficiente | Canal local oculto, mínimo privilegio, límites de entorno, no persistencia ni reenvío entre orígenes |
| Media | Flujo rígido orientado solo a PDF | Entrada URL-first, diagnóstico si falta objetivo, selección por intención y referencias bajo demanda |

## Arquitectura elegida

Núcleo portable `SKILL.md` + referencias temáticas + scripts PDF existentes. No nuevo servidor, framework de agentes, memoria externa ni dependencia de una marca. El agente conserva un resumen por sitio/identidad durante la sesión; no vuelca índice completo al contexto ni persiste secretos. Revalida cuando cambian las condiciones.

El CLI no representa toda la capacidad de la SKILL: scripts para tareas deterministas repetidas, herramientas HTTP nativas para REST general. Esta decisión evita duplicar un SDK de escritura en dos lenguajes. Las reglas de seguridad conversacionales no son un sandbox: se suman a permisos del agente y controles reales de WordPress.

## Compatibilidad y límites

El estándar unifica el formato, no herramientas, permisos ni garantía de selección implícita. Se documentan rutas por plataforma y una alternativa explícita de lectura del archivo. No se modifican configuraciones globales del estudiante ni se instalan servicios.

Las pruebas locales de respuestas HTTP controladas no equivalen a probar varias instalaciones reales. Las sesiones de interpretación tampoco prueban descubrimiento automático, credenciales o publicación end-to-end. La evidencia actual y sus límites se registran por separado en `REVISION.md`; la histórica permanece en `RESULTADOS.md`.
