# Skill de scraping de YouTube

Guía humana de uso. La skill recupera **metadatos**, **transcripción** y **comentarios** de un video de YouTube con Python, sin cuenta, sin API key y sin scraper autenticado. Todo lo descrito acá se ejecutó y se verificó el 22-10-2026 en Windows (Python 3.13).

## Qué hay en esta carpeta

| Archivo | Qué es |
|---|---|
| `SKILL.md` | Contrato para agentes de IA (activación, reglas, decisiones). No es documentación humana. |
| `README.md` | Esta guía. |
| `assets/yt_datos.py` | CLI ejecutable: `metadatos`, `transcripcion`, `comentarios`, `todo`. |
| `references/api-oficial.md` | Data API v3 de Google: endpoints, cuotas, autenticación y qué no cubre. |
| `references/alternativas.md` | InnerTube, `yt-dlp`, `youtube-transcript-api`, Invidious/Piped, con los límites observados. |
| `references/etica-legal.md` | Checklist antes de publicar un dataset de comentarios o transcripciones. |

## Instalación

```bash
python -m pip install -r youtube-api/assets/requirements.txt
```

Los comandos de esta guía se ejecutan desde la raíz del repositorio; si la skill está instalada sola, quitar el prefijo `youtube-api/`.

## Uso rápido

```bash
# Metadatos del video
python youtube-api/assets/yt_datos.py metadatos \
  --url "https://www.youtube.com/watch?v=j3ZIM9UaXlE" --out datos

# Transcripción con marca de tiempo (JSON + CSV)
python youtube-api/assets/yt_datos.py transcripcion \
  --url "https://www.youtube.com/watch?v=j3ZIM9UaXlE" --lang es --out datos

# Comentarios: lista completa, con respuestas
python youtube-api/assets/yt_datos.py comentarios \
  --url "https://www.youtube.com/watch?v=j3ZIM9UaXlE" --max 400 --con-respuestas --out datos

# Las tres cosas en una pasada
python youtube-api/assets/yt_datos.py todo \
  --url "https://www.youtube.com/watch?v=j3ZIM9UaXlE" --out datos
```

Acepta URL completa (`watch?v=`, `youtu.be/`, `shorts/`) o el ID de 11 caracteres. `--help` en cualquier subcomando muestra las opciones.

## Qué devuelve

**Metadatos** (`<id>_metadatos.json`): título, canal, `canal_id`, vistas, likes, duración, descripción, palabras clave, categoría, fechas de publicación y subida, y si estaba en vivo.

**Transcripción** (`<id>_transcripcion.json` y `.csv`): `segmentos` con `inicio`, `duracion` y `texto` por fragmento, más el `texto` completo. El campo `automatica` indica si el subtítulo es transcripción automática (ASR).

**Comentarios** (`<id>_comentarios.json` y `.csv`): `comment_id`, `autor`, `autor_canal_id`, `autor_es_creador`, `texto`, `publicado`, `likes`, `respuestas`, `nivel` y `respuesta_a` (el comentario padre cuando es respuesta). Además `comentarios_declarados` (lo que dice la página) frente a `obtenidos` (lo que se recolectó).

## Detalles que conviene conocer

| Tema | Comportamiento verificado |
|---|---|
| Orden de comentarios | `--orden newest` recorre la lista completa (168 de primer nivel en el video de ejemplo). `--orden top` reproduce la jerarquía de la interfaz y devuelve un subconjunto (154). |
| Respuestas | `--con-respuestas` agrega las respuestas de cada hilo, paginando dentro de cada hilo. Convierte 168 de primer nivel en 229 filas. |
| Transcripción | Se pide la URL firmada que devuelve la pista de subtítulo. Modificarla (agregar `fmt=json3`) no cambia la respuesta: el servidor devuelve XML `timedtext`. |
| Subtítulos | El video de ejemplo solo tiene subtítulos automáticos (ASR) en ar, en, pt y es. No hay subtítulo manual. |
| Bloqueos | Si aparece `LOGIN_REQUIRED` con "Sign in to confirm you're not a bot", la IP está bloqueada. No hay modo de sortearlo: usar otra red o `yt-dlp` más tarde. |
| `PoTokenRequired` | La transcripción puede fallar si la URL de subtítulo exige *proof of origin* token. Es intermitente; `yt-dlp` tiene respaldo. |
| Videos no disponibles | El CLI informa el estado del reproductor y sale con código 1, sin escribir archivos. |

## Alternativas cuando el CLI falla

```bash
# Metadatos completos
yt-dlp --skip-download --dump-single-json "URL"

# Subtítulos automáticos en VTT
yt-dlp --skip-download --write-auto-subs --sub-langs es --sub-format vtt -o "v.%(ext)s" "URL"

# Comentarios con respuestas
yt-dlp --skip-download --write-comments \
  --extractor-args "youtubecomment:max_comments=all,all,all;max_replies=all" \
  --print "%(comments)j" --no-simulate "URL"
```

Detalles y límites en `references/alternativas.md`.

## Uso responsable

- Antes de publicar un dataset de comentarios o transcripciones, revisar `references/etica-legal.md`.
- Los comentarios son datos personales: minimizar y anonimizar.
- La transcripción es una obra protegida: se cita la fuente, no se redistribuye el texto como propio.
- Indicar siempre método, fecha de captura y cobertura en el informe.

## Siguiente paso

Leé `SKILL.md` si vas a delegar esta tarea a un agente de IA, y `references/api-oficial.md` si necesitás la vía documentada por Google con clave y cuota.
