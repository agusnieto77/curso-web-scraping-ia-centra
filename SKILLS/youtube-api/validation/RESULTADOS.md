# youtube-api · Resultados de la prueba

Ejecución real del 22-10-2026 en Windows (Python 3.13.16, `requests` 2.34.2). Video testigo: `j3ZIM9UaXlE`, "La IA debería hacernos trabajar menos (NO MÁS)", canal midudev, publicado el 21-10-2026.

## Qué se ejecutó

| Comando | Resultado |
|---|---|
| `yt_datos.py metadatos --url <watch?v=j3ZIM9UaXlE>` | 18 campos; 77 412 vistas, 1 765 likes, 604 s, categoría "Science & Technology" |
| `yt_datos.py transcripcion --url ... --lang es` | 305 segmentos, idioma `es`, `automatica=true` |
| `yt_datos.py transcripcion --url ...` (sin `--lang`) | 305 segmentos en `es`: la pista por defecto prefiere idioma del cliente |
| `yt_datos.py comentarios --url ... --max 60` | 60 comentarios |
| `yt_datos.py comentarios --url ... --max 400 --con-respuestas` | 230 comentarios de 230 declarados (168 de primer nivel + 62 respuestas). En una corrida anterior fueron 229 de 229 (168 + 61): el video seguia recibiendo comentarios |
| `yt_datos.py comentarios --url ... --max 400 --con-respuestas --orden top` | 208 comentarios (154 de primer nivel + 54 respuestas): el criterio "Destacados" es un subconjunto |
| `yt_datos.py todo --url ... --max 400 --con-respuestas` | las tres salidas en una pasada, mismos conteos |
| `yt_datos.py metadatos --url <id inexistente>` | error informativo con el estado del reproductor; código de salida 1; sin archivos escritos |
| `yt_datos.py metadatos --url no-es-un-id` | error de validación del ID |
| `python validation/test_yt_datos.py` | 23 pruebas, todas OK (versión 1.0). Tras la revisión 1.1: 30 pruebas OK |

## Revisión 1.1 (22-10-2026, misma máquina)

| Comando | Resultado |
|---|---|
| `todo --url <j3ZIM9UaXlE> --max 400 --con-respuestas` | metadatos (88 080 vistas), 305 segmentos `es` automáticos, 254 de 254 comentarios; una sola descarga de la ficha |
| `comentarios --url <j3ZIM9UaXlE> --max 400 --con-respuestas` (tras el fix) | 255 de 255 declarados: el video sigue recibiendo comentarios |
| `comentarios --url youtu.be/... --orden top` | 175 de 254: "Destacados" es un subconjunto |
| `metadatos --url dQw4w9WgXcQ` (segundo video, otro canal e idioma) | título y 1 829 270 700 vistas |
| `transcripcion --url dQw4w9WgXcQ --lang en` | 61 segmentos, subtítulo **manual** (`automatica=false`) |
| `comentarios --url dQw4w9WgXcQ --max 40` | 40 de **2 460 280** declarados. Antes del fix se informaban 24, porque se leía el contador abreviado "2,4 M" |

## Comparación con otras vías

| Vía | Comentarios obtenidos | Nota |
|---|---|---|
| CLI de la skill (`--orden newest`) | 230 de 230 declarados | 168 de primer nivel + 62 respuestas |
| CLI de la skill (`--orden top`) | 208 | Jerarquía de la interfaz: subconjunto |
| `yt-dlp` con `max_comments=all,all,all;max_replies=all` | 228 | 168 de primer nivel + 60 respuestas; el hilo de un comentario no se publica en la interfaz |
| Data API v3 sin clave | HTTP 403 "Method doesn't allow unregistered callers" | Confirma que la vía oficial exige identidad registrada |

## Hallazgos que sostienen el diseño

1. **El cliente `ANDROID` de InnerTube es el que funciona.** Con `clientName=WEB`, `youtubei/v1/player` responde `playabilityStatus: UNPLAYABLE`; con `ANDROID` (20.10.38) responde `OK` y trae `captions`.
2. **La URL de subtítulo es firmada y no admite parámetros.** Agregar `fmt=json3` devuelve el mismo XML `timedtext` (81 056 bytes) porque la firma cubre los parámetros de la consulta.
3. **"Destacados" y "Más recientes" recorren conjuntos distintos.** 154 frente a 168 comentarios de primer nivel; la unión es 168. Por eso el valor por defecto es `newest`.
4. **Los comentarios vienen en `frameworkUpdates.entityBatchUpdate.mutations`.** El texto no está en el hilo: se enlaza por `commentKey`, y la entidad de payload se reconoce porque su `entityKey` es prefijo del `commentKey`. Sin esa unión el resultado es cero.
5. **Las respuestas viven en un endpoint aparte** (`getCommentRepliesEndpoint`), paginado dentro del hilo, y con el token anidado en el botón "Mostrar más respuestas", no en el `continuationEndpoint` directo.
6. **`captions.list` de la Data API v3 no sirve para videos ajenos**: exige OAuth con `youtube.force-ssl` y cuesta 50 unidades; la transcripción de terceros sale por `timedtext`.

## Límites observados

- La vía interna no tiene contrato: la estructura de la respuesta cambió durante 2026 (`commentRenderer` → `commentViewModel` + `commentEntityPayload`).
- Sin clave de API, la vía oficial no responde; con clave propia, la cuota por defecto son 10 000 unidades/día y `search.list` consume 100 por llamada.
- Las instancias públicas de Invidious y Piped estaban caídas o bloqueadas por IP el día de la prueba (500, 403, 401, 526, 502).
- `youtube-transcript-api` puede fallar con `PoTokenRequired` cuando la URL de subtítulo incluye `exp=xpe`.
- La red de la prueba no fue bloqueada. Ante `LOGIN_REQUIRED` con "Sign in to confirm you're not a bot" el CLI informa el bloqueo y no intenta sortearlo.
