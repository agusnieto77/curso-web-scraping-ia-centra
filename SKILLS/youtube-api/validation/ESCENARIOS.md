# Escenarios de validación de youtube-api

Criterios reproducibles para revisar el CLI y sus documentos. No afirma ejecución de agentes: describe qué debe comprobarse cuando se ejecuta.

## Pruebas puras (sin red)

| Escenario | Criterio de aceptación |
|---|---|
| ID desde URL `watch?v=` | `extraer_id_video` devuelve los 11 caracteres |
| ID desde URL `youtu.be/` | devuelve el mismo ID |
| ID desde URL `shorts/` | devuelve el mismo ID |
| ID suelto de 11 caracteres | se acepta tal cual |
| URL inválida | lanza `YouTubeError` con mensaje claro, sin excepción cruda |
| XML `timedtext` formato 3 (`<p t d><s>`) | devuelve segmentos con `inicio` y `duracion` en segundos |
| XML `timedtext` formato 1 (`<text start dur>`) | devuelve segmentos equivalentes |
| XML corrupto | lanza `YouTubeError` en vez de `ParseError` |
| Comentario con entidad desalineada | se localiza por prefijo de `entityKey` |
| Cabecera con `commentsCount` en `runs` | `_contar_comentarios` devuelve el entero |

## Pruebas de red (requieren internet y una IP no bloqueada)

| Escenario | Criterio de aceptación |
|---|---|
| Metadatos de un video público | devuelve título, canal, vistas, likes y fecha de publicación |
| Video inexistente | error informativo con el estado del reproductor; código de salida 1; sin archivos escritos |
| Video restringido por edad | error informativo; no intenta esquivar la restricción |
| Transcripción en español | devuelve segmentos con texto e idioma `es`; `automatica` refleja si es ASR |
| Transcripción en idioma inexistente | error que lista los idiomas disponibles |
| Video sin subtítulos | error explícito; no escribe JSON vacío |
| Comentarios con `--orden newest` | `obtenidos` igual a la lista completa declarada (168 de primer nivel en el video de ejemplo) |
| Comentarios con `--orden top` | devuelve el subconjunto de la jerarquía de la interfaz (154 en el video de ejemplo) |
| Comentarios con `--con-respuestas` | agrega respuestas con `respuesta_a` y `nivel` 1 |
| Cobertura | `obtenidos` se compara con `comentarios_declarados` y se reporta la diferencia |
| Video sin comentarios | error que lo distingue de "comentarios vacíos" |
| Repetición de la misma corrida | los archivos se regeneran idénticos salvo `capturado_en_utc` |

## Criterios transversales

- No afirmar cobertura total si `obtenidos` es menor que `comentarios_declarados`.
- No presentar datos obtenidos por InnerTube como salida de la Data API v3.
- No reintentar en bucle ante un bloqueo por IP; informar y proponer la vía alternativa.
- Toda afirmación sobre cifras del ejemplo se apoya en la ejecución registrada en [RESULTADOS.md](RESULTADOS.md).
