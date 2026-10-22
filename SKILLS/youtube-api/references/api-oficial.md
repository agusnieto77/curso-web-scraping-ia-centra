# API oficial de YouTube (Data API v3)

Ruta documentada por Google para datos de video y comentarios. Requiere proyecto en Google Cloud, habilitación de la API y una **API key** (o credenciales OAuth 2.0). Todo lo que sigue se contrastó con la documentación vigente y con respuestas reales del 22-10-2026.

## Qué resuelve y qué no

| Objetivo | Endpoint oficial | Notas |
|---|---|---|
| Metadatos de un video | `GET /youtube/v3/videos?part=snippet,statistics,contentDetails&id=VIDEO_ID` | `snippet` (título, descripción, etiquetas, `publishedAt`), `statistics` (vistas, likes), `contentDetails` (duración, `caption` = "true"/"false") |
| Buscar videos | `GET /youtube/v3/search?part=snippet&q=...&type=video` | Costo de cuota: **100 unidades** por llamada |
| Comentarios (hilos) | `GET /youtube/v3/commentThreads?part=snippet,replies&videoId=VIDEO_ID&maxResults=100` | Costo: **1 unidad** por llamada. `maxResults` admite hasta 100; paginar con `pageToken` |
| Respuestas a un comentario | `GET /youtube/v3/comments?part=snippet&parentId=...` | Costo: **1 unidad**. `comments.list` devuelve también las respuestas cuando se pide `part=replies` en `commentThreads` |
| Pistas de subtítulo | `GET /youtube/v3/captions?part=snippet&videoId=VIDEO_ID` | Costo: **50 unidades**. **Requiere OAuth** con `youtube.force-ssl` o `youtubepartner` |
| Descargar subtítulo | `GET /youtube/v3/captions/download` | **No entrega el texto**: devuelve un archivo que contiene una URL de `timedtext`; hay que seguir esa URL |

Puntos que surprises en la práctica:

- `captions.list` **solo funciona con el canal propietario o con OAuth autorizado**. Un atacante anónimo con API key propia no puede leer la transcripción de un video ajeno por esta vía.
- La API oficial **no expone el texto de los comentarios en el sense de búsqueda**: `commentThreads.list` sí los devuelve, pero sin filtros de texto y con el mismo costo por página.
- `search.list` es la operación más cara: 100 unidades por llamada frente a 1 unidad por página de comentarios. Con la cuota por defecto de 10 000 unidades/día, 100 búsquedas agotan la cuota diaria.
- La cuota por defecto es **10 000 unidades/día**; se puede pedir aumento en la consola de Google Cloud.

## Autenticación

- **API key** (simple): suficiente para `videos.list`, `commentThreads.list`, `comments.list` y `search.list` sobre contenido público.
- **OAuth 2.0**: necesario para `captions.list`/`captions.download` y para recursos privados o del propio canal. Scope mínimo para subtítulos: `https://www.googleapis.com/auth/youtube.force-ssl`.

La API key viaja en el parámetro `key=` de la query. No pegarla en el chat ni en archivos versionados: va en variable de entorno (`YOUTUBE_API_KEY`) o en el gestor de secretos del entorno.

## Comprobación rápida

Sin clave, la API responde 403 con un mensaje explícito:

```json
{
  "error": {
    "code": 403,
    "message": "Method doesn't allow unregistered callers (callers without established identity). Please use API Key or other form of API consumer identity to call this method."
  }
}
```

Ese 403 **no** significa que falten permisos sobre el video: significa que la llamada no está identificada. Con una clave válida, un video inexistente devuelve 404 `videoNotFound` y un video privado devuelve 403 `forbidden`.

## Comparación con la vía no oficial

| Aspecto | Data API v3 | InnerTube (`youtubei`) |
|---|---|---|
| Clave | Obligatoria | No: la clave pública se lee del propio HTML |
| Cuota | 10 000 unidades/día por defecto | Sin cuota documentada, pero sujeto a bloqueos por IP |
| Soporte | Sí (Google) | No: puede cambiar sin aviso |
| Comentarios | Sí, paginados | Sí, paginados |
| Transcripción de videos ajenos | No (`captions` exige OAuth del propietario) | Sí, por `timedtext` |

Para una clase o un análisis puntual, la vía no oficial es la práctica (es la que usa `yt-dlp`). Para un sistema en producción, la oficial. Lo que no corresponde es presentar la segunda como la primera.
