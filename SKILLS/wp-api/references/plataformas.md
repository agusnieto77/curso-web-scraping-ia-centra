# Instalación y adaptación por agente

Una misma carpeta con `SKILL.md`, referencias y scripts. El formato Agent Skills no estandariza las herramientas HTTP, permisos de ejecución o selección automática del modelo. No bifurcar las reglas de WordPress para cada producto.

## Ubicaciones e invocación

| Producto | Proyecto | Personal | Activación |
|---|---|---|---|
| Codex CLI/IDE | `.agents/skills/wp-api/` | `~/.agents/skills/wp-api/` | `$wp-api`, `/skills`, o petición natural |
| Claude Code | `.claude/skills/wp-api/` | `~/.claude/skills/wp-api/` | `/wp-api` o petición natural |
| OpenCode | `.opencode/skills/wp-api/`, `.agents/skills/wp-api/` o `.claude/skills/wp-api/` | `~/.config/opencode/skills/`, `~/.agents/skills/` o `~/.claude/skills/`, con subcarpeta del nombre | Pedir la skill por nombre; herramienta nativa `skill({name: "wp-api"})` |
| Otro compatible | Consultar ubicación del producto | Consultar ubicación del producto | Selector nativo o lectura explícita del archivo |

`~` significa carpeta personal; no copiar literalmente una ruta Linux a PowerShell. Priorizar instalación por proyecto para el curso. No instalar la misma skill en varias ubicaciones detectadas por un agente; los productos difieren en precedencia y manejo de duplicados.

En OpenCode el comando slash es opcional según versión y `metadata["opencode/slash"] = "true"`. Esta SKILL no lo declara: usar el nombre en lenguaje natural es la vía documentada aquí. No presentar `/skill-name` como sintaxis universal.

## Copiar la carpeta completa

Desde la carpeta que contiene el clon `SKILLS`, PowerShell para Codex/OpenCode:

```powershell
New-Item -ItemType Directory -Force .agents\skills\wp-api | Out-Null
Copy-Item -Recurse -Force SKILLS\wp-api\* .agents\skills\wp-api\
```

POSIX:

```sh
mkdir -p .agents/skills/wp-api
cp -R SKILLS/wp-api/. .agents/skills/wp-api/
```

Para Claude reemplazar `.agents` por `.claude`. Copiar encima actualiza archivos pero no elimina archivos obsoletos; al actualizar revisar la copia instalada. Si se usan enlaces simbólicos para mantener una sola fuente, comprobar soporte de la versión y permisos del sistema; no son requisito del curso.

## Sin instalación nativa

Un agente con lectura de archivos puede recibir:

> Leé `SKILLS/wp-api/SKILL.md` y las referencias pertinentes. En https://symaga.com buscá el catálogo de silos granja y mostrame título y enlace sin descargarlo.

Esto es carga explícita por archivo, no activación nativa ni implícita. Si no puede leer archivos ni usar HTTP, explicar la limitación; no fingir ejecución.

## Capacidades necesarias, no nombres de herramientas

- Lectura local: cargar SKILL y solo referencias necesarias.
- HTTP: consultar índice, cabeceras, JSON, esquema y contenido. Un lector web que oculta cabeceras o estado puede no bastar: preferir cliente HTTP real disponible.
- Terminal opcional: ejecutar Python/R para medios de cualquier formato y exportación JSON; resolver rutas desde la carpeta de la SKILL.
- Pregunta/confirmación: usar la UI nativa o conversación; no automatizar un “sí”.
- Secretos: canal local oculto o almacén seguro. Si no existe, no ejecutar autenticación desde el chat.

No declarar `allowed-tools` específico ni inyección de comandos `!` como dependencia del núcleo. No desactivar sandbox ni preaprobar escrituras para “hacer funcionar” la skill. Los permisos del agente y los de WordPress son controles distintos.

## Verificar instalación

1. Reabrir agente si la skill no aparece.
2. Pedir que la cargue y cite el archivo leído; verificar selector o llamada nativa si existe.
3. Probar prompt natural sin nombre y observar si la carga; si no, usar invocación explícita.
4. Probar consulta pública acotada. Para probar privados/escritura, usar staging autorizado y seguir los escenarios; una respuesta textual no verifica una operación remota.

Fuentes: [especificación](https://agentskills.io/specification), [Codex](https://developers.openai.com/codex/skills), [Claude Code](https://code.claude.com/docs/en/skills), [OpenCode](https://opencode.ai/docs/skills/). La compatibilidad documentada no equivale a haber ejecutado todos los clientes y versiones; consultar `validation/REVISION.md`.
