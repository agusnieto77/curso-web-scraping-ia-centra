---
name: youtube-api
description: "Trigger: scraping de YouTube, recuperar datos, metadatos, transcripción, subtítulos o comentarios de un video, API de YouTube, InnerTube, Innertube, yt-dlp, youtube-transcript-api, timedtext."
license: Apache-2.0
compatibility: Python >= 3.10 con requests. Sin cuenta ni API key; funciona en cualquier cliente de Agent Skills con shell y HTTP.
metadata:
  author: "agusnieto77"
  version: "1.1"
---

## Activation Contract

Activar al pedir datos, metadatos, texto transcrito o comentarios de un video de YouTube (por URL o por ID), o al preparar demos y material docente sobre extracción en YouTube.

## Hard Rules

- Lectura pública y anónima por defecto. No enviar credenciales, cookies de sesión ni tokens de usuario; no resolver CAPTCHAs ni evadir bloqueos. Si YouTube exige sesión o devuelve estado no reproducible, informar el bloqueo.
- Distinguir la vía **oficial** (Data API v3, requiere clave de proyecto y cuota) de la vía **no oficial** (API interna `youtubei` / InnerTube). Declarar siempre cuál se usó: no presentar datos de InnerTube como salida de la API documentada.
- La transcripción obtenida por InnerTube o `timedtext` es un subtítulo (a menudo automático, ASR): no es la fuente original del guion. Marcar `automatica=true` y conservar el idioma.
- Los comentarios son datos personales: conservar solo lo necesario, atribuir el autor solo si el objetivo del análisis lo requiere y anonimizar al publicar.
- No publicar datasets de comentarios ni transcripciones sin el checklist de [ética-legal](references/etica-legal.md).
- Verificar la cobertura: `obtenidos` frente a `comentarios_declarados`. Un subconjunto no es "todos los comentarios".

## Decision Gates

| Necesidad | Acción |
|---|---|
| Metadatos (título, canal, vistas, likes, fecha, categoría, descripción) | `metadatos` del CLI: `ytInitialPlayerResponse` de la ficha pública |
| Texto del video (transcripción con tiempos) | `transcripcion`: `youtubei/v1/player` + `timedtext`; alternativa `yt-dlp --write-auto-subs` |
| Comentarios de primer nivel | `comentarios --orden newest` (lista completa) |
| Comentarios destacados (jerarquía de la interfaz) | `comentarios --orden top` |
| Respuestas a comentarios | `comentarios --con-respuestas` (hilo por hilo) |
| Búsqueda de videos o canal | `youtubei/v1/search` y `youtubei/v1/browse`; alternativa `yt-dlp "ytsearch10:..."` |
| Proyecto con cuota y clave propia | Data API v3 (`videos.list`, `commentThreads.list`, `captions.list`): ver [api-oficial](references/api-oficial.md) |
| API oficial sin clave, o transcripción no disponible por InnerTube | `yt-dlp` con extractor `youtube`; ver [alternativas](references/alternativas.md) |

## Execution Steps

1. Identificar el video: aceptar URL completa (`watch?v=`, `youtu.be/`, `shorts/`) o ID de 11 caracteres; el CLI normaliza ambos.
2. Elegir la vía: empezar por el CLI incluido (`assets/yt_datos.py`), que no requiere clave ni cuenta. Cargar [alternativas](references/alternativas.md) solo si falla o si se necesita búsqueda por canal.
3. Ejecutar por partes: `metadatos`, `transcripcion`, `comentarios`, o `todo` en una sola pasada. Salida en JSON y CSV en la carpeta indicada.
4. Para comentarios, preferir `--orden newest` cuando el objetivo sea cobertura completa; `--orden top` reproduce lo que ve un usuario en la interfaz.
5. Registrar método, hora de captura (`capturado_en_utc`), cobertura y límites junto a los datos.
6. Si una vía falla (bloqueo, estado no reproducible, subtítulos vacíos), informarlo y probar la alternativa documentada; no simular ni rellenar datos.

## Output Contract

Entregar: JSON y CSV con metadatos, transcripción segmentada y comentarios (con `comment_id`, autor, texto, fecha, likes, respuestas y nivel de anidamiento), más una nota breve con método usado, cobertura (`obtenidos`/`comentarios_declarados`), fecha de captura y límites observados. No presentar planes, fixtures ni evidencia histórica como ejecución actual.

## References

- [API oficial](references/api-oficial.md) — Data API v3: endpoints, cuotas, autenticación y qué **no** cubre.
- [Alternativas](references/alternativas.md) — InnerTube, `yt-dlp`, `youtube-transcript-api`, Invidious/Piped y sus límites reales.
- [Ética y legalidad](references/etica-legal.md) — qué es dato público y qué no, y qué revisar antes de publicar.
- [Guía de uso](README.md) — instalación, comandos y errores frecuentes.
