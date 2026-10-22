# Alternativas para obtener datos de YouTube

Todas las vías verificadas el 22-10-2026 contra el video `j3ZIM9UaXlE` ("La IA debería hacernos trabajar menos (NO MÁS)", canal midudev). Lo que sigue describe el comportamiento observado, no lo que promete cada documentación.

## 1. API interna `youtubei` (InnerTube)

Es la API que usa el propio reproductor de YouTube. Se llama sin cuenta: la clave pública (`INNERTUBE_API_KEY`) y la versión de cliente se leen del HTML de la ficha.

| Endpoint | Qué devuelve | Observado |
|---|---|---|
| `POST /youtubei/v1/player` | Metadatos (`videoDetails`, `microformat`) y pistas de subtítulo (`captions`) | Con cliente `ANDROID` (`clientVersion` 20.10.38) responde `playabilityStatus: OK`; con cliente `WEB` responde `UNPLAYABLE` |
| `POST /youtubei/v1/next` | Sección de comentarios y continuaciones | Paginación por token de continuación |
| `POST /youtubei/v1/search` | Resultados de búsqueda | `query` más contexto de cliente |
| `POST /youtubei/v1/browse` | Contenido de canal o lista | `browseId` con el ID de canal |
| `GET /api/timedtext` | XML de subtítulos (`timedtext` formato 1 o 3) | La URL base viene firmada en la pista de subtítulo; no se puede armar a mano |

Claves que hacen funcionar la vía:

- El **cliente `ANDROID`** es el que devuelve `OK` en `player`. Con `WEB` el mismo endpoint responde `UNPLAYABLE` (detección de automatización). Cambiar `clientName` cambia el resultado.
- La transcripción se pide **con la URL base que devuelve la pista**, sin modificarla: agregar `fmt=json3` no cambia la respuesta, porque la firma cubre los parámetros. En la práctica el servidor devuelve siempre XML `timedtext`.
- Las respuestas a comentarios viven en `frameworkUpdates.entityBatchUpdate.mutations` con `commentEntityPayload`; el hilo y la respuesta se enlazan por `commentKey`, y la entidad de payload se reconoce porque su `entityKey` es **prefijo** del `commentKey`.

### Orden de comentarios

El token de continuación inicial (sección `comment-item-section`) devuelve la lista en el criterio por defecto. La cabecera (`commentsHeaderRenderer`) publica dos tokens de clasificación:

| Criterio | Token | Cobertura observada (229 comentarios declarados) |
|---|---|---|
| "Destacados" (`sortMenu.subMenuItems[0]`) | `continuationCommand` de la sección de orden | 154 comentarios de primer nivel: es la jerarquía de la interfaz, un subconjunto |
| "Más recientes" (`sortMenu.subMenuItems[1]`) | `continuationCommand` de la sección de orden | 168 comentarios de primer nivel: recorre la lista completa |

La unión de ambos criterios da 168: "Destacados" está contenido en "Más recientes". Para cobertura completa usar "Más recientes"; para replicar lo que ve un usuario en pantalla, "Destacados".

### Límites

- Las IP de datacenter y las proxies son las que primero se bloquean. Cuando aparece `LOGIN_REQUIRED` con motivo `Sign in to confirm you're not a bot`, la respuesta es un bloqueo: se informa, no se intenta esquivar.
- La estructura de la respuesta cambia sin aviso (esto pasó varias veces durante 2026: `commentRenderer` pasó a `commentViewModel` más `commentEntityPayload`).
- No hay contrato ni garantía de estabilidad. Es la vía que usa `yt-dlp`, y `yt-dlp` también se rompe.

## 2. `yt-dlp`

Herramienta de línea de comandos que ya resuelve las tres salidas:

```bash
# Metadatos (JSON con todos los campos disponibles)
yt-dlp --skip-download --dump-single-json "https://www.youtube.com/watch?v=ID"

# Subtítulos automáticos en VTT
yt-dlp --skip-download --write-auto-subs --sub-langs es --sub-format vtt -o "v.%(ext)s" "URL"

# Comentarios (hilos + respuestas)
yt-dlp --skip-download --write-comments \
  --extractor-args "youtubecomment:max_comments=all,all,all;max_replies=all" \
  --print "%(comments)j" --no-simulate "URL"
```

Observado: 228 comentarios (168 de primer nivel + 60 respuestas) frente a los 229 declarados por la página; la diferencia es un comentario cuyo hilo no se publica en la interfaz. El orden por defecto de `yt-dlp` es "Más recientes", de ahí que su cobertura coincida con ese criterio.

Advertencia habitual: `WARNING: [youtube] No supported JavaScript runtime could be found`. YouTube va exigiendo un runtime JavaScript (Deno) para resolver formatos. No afecta a metadatos, subtítulos ni comentarios, pero sí a la descarga de video.

## 3. `youtube-transcript-api`

```python
from youtube_transcript_api import YouTubeTranscriptApi
api = YouTubeTranscriptApi()
pistas = api.list("j3ZIM9UaXlE")           # ar, en, pt, es (todos ASR)
tr = pistas.find_transcript(["es", "en"]).fetch()
```

- Devuelve los segmentos con `start` y `duration`: mismo contenido que `timedtext`, con la API más cómoda.
- Usa por dentro el mismo `youtubei/v1/player` con cliente `ANDROID`.
- **Falla con `PoTokenRequired`** cuando la URL de subtítulo incluye `exp=xpe`: es el requisito de *proof of origin* token. Ocurre de forma intermitente según la sesión y el video.
- La versión 1.x cambió la API: `YouTubeTranscriptApi()` instancia y `api.list()` / `api.fetch()`; las funciones de módulo de la 0.x están deprecadas.

## 4. Instancias de Invidious y Piped

Proxy web que expone una API JSON propia (`/api/v1/videos/ID`, `/streams/ID`).

Estado observado de las instancias públicas el 22-10-2026:

| Instancia | Respuesta |
|---|---|
| `invidious.f5.si` | HTTP 500 |
| `inv.nadeko.net`, `yewtu.be` | HTTP 403 |
| `invidious.nerdvpn.de` | HTTP 401 |
| `pipedapi.kavin.rocks` | HTTP 526 |
| `pipedapi.adminforge.de` | HTTP 403 |
| `pipedapi.reallyaweso.me` | HTTP 502 |

Es decir: las instancias públicas están degradadas o bloquean por IP. No conviene basar una clase o una recolección en ellas; si se usan, verificar cada vez la instancia concreta y tener la vía directa como plan B.

## 5. `oEmbed`

`GET https://www.youtube.com/oembed?url=URL&format=json` devuelve, sin clave y sin paginación: título, autor, URL del canal, miniatura y el `iframe` de inserción. Sirve para identificar un video o montar un embed, no para analizar contenido.
