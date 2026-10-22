# Changelog

## 1.1 — 2026-10-22

- `todo` descarga la ficha `watch` y consulta `youtubei/v1/player` una sola vez por video (antes, tres y dos veces): caché por cliente.
- El JSON embebido (`ytInitialPlayerResponse`, `ytInitialData`) se decodifica con `raw_decode` desde la llave de apertura; el regex anterior cortaba en el primer `};` dentro de un string.
- `Retry-After` con fecha HTTP ya no rompe la espera ante HTTP 429 (se usa la espera por defecto, acotada a 30 s).
- Skill renombrada de `youtube-scraping` a `youtube-api` para coincidir con su carpeta; rutas de la documentación corregidas.
- Mensaje de error de subtítulos: "PO token (proof of origin)".
- `comentarios_declarados` usa el total exacto (`countText`) en lugar del abreviado: en videos con millones de comentarios ("2,4 M") el valor anterior era 24. Las formas abreviadas (`mil`, `M`, `K`) se interpretan cuando no hay total exacto.
- 7 pruebas nuevas (30 en total), incluido un cliente con sesión falsa.

## 1.0 — 2026-10-22

Primera versión: CLI `assets/yt_datos.py` con `metadatos`, `transcripcion`, `comentarios` (orden `newest`/`top`, respuestas por hilo) y `todo`, vía InnerTube y páginas públicas, sin cuenta ni API key. Referencias de la Data API v3, alternativas (`yt-dlp`, `youtube-transcript-api`, Invidious/Piped) y ética.
