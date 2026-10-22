# Validación de la revisión multi-formato (v3)

Evidencia de la revisión de octubre de 2026 que generaliza la skill de PDF a **todos los formatos de la biblioteca de medios** y añade **exportación JSON/NDJSON de colecciones REST**, con paridad Python/R. No se realizaron escrituras en SYMAGA ni se usaron credenciales WordPress. `RESULTADOS.md` conserva la prueba histórica; los conteos no se reutilizan como resultados actuales.

## Entorno observado

- Windows; Python 3.13.16, requests 2.34.2, truststore del sistema (`tls: system`); `pypdf` ausente (opcional: conteo de páginas reporta vacío).
- R 4.6.1 por ruta absoluta (`C:/Program Files/R/R-4.6.1/bin/x64/Rscript.exe`), no en PATH; `httr2`, `jsonlite`, `digest`, `pdftools` disponibles. Advertencias de locale `C.UTF-8` en consola.

## Qué cambió (v2 → v3)

- CLI unificado `media`/`download`/`export`/`verify` (antes `pdfs`/`download` solo PDF): registro MIME con ~75 tipos de WordPress, alias de extensión (`--mime pdf,jpg`), familias de destino (`documentos/`, `datos/`, `imagenes/`, `audio/`, `video/`, `comprimidos/`, `otros/`) y firmas de bytes por formato.
- Validación en tres capas para cualquier formato: Content-Type (esperado/genérico/misma familia; HTML nunca), firma de bytes mágicos (incluye JSON parseado, SVG, tar en offset 257, OLE, ftyp, EBML...) y SHA-256. Estados nuevos `descargado`/`reutilizado`/`exportado`/`tipo_inesperado`; los históricos `*_pdf` siguen verificándose.
- `export`: atajos y rutas relativas (`wc/v3/products`), filtros, `_fields`, `--id`, JSON con envoltura o NDJSON, colecciones objeto envueltas con `__clave`, error WP ≠ colección vacía, freno por **solicitudes estimadas** antes de consultar.
- Reintentos de lectura (429/5xx/red) con `Retry-After` acotado a 20 s en ambos lenguajes; redirecciones de descarga solo same-origin.
- Huella de exportación canónica compartida Python/R: el mismo recurso con los mismos filtros produce el mismo archivo y una sola fila de manifiesto en corridas de ambos lenguajes.

## Resultado de suites y smoke

| Comprobación | Resultado observado |
|---|---|
| Suite Python `test_wp_api.py` | **69 pruebas OK**: registro MIME, firmas de 30+ formatos, content-type, descarga pdf→`documentos`/png→`imagenes`/json→`datos`, reutilización por hash, trampa HTML (200 `text/html` → `tipo_inesperado`; HTML con `application/pdf` → `invalido` y archivo eliminado), export json/ndjson/`--id`/colección objeto/error WP/freno por solicitudes, verify mixto con estados históricos, reintentos, descubrimiento y redirecciones |
| Harness HTTP local `test_scenarios.py` | **13 pruebas OK** con servidor real 127.0.0.1: descubrimiento (raíz, `/blog`, `?rest_route=`), 401/403/404/red caída, `media --mime` (filtro, alias, desconocido → exit 2), descarga multi-formato end-to-end + segunda corrida `reutilizado`, trampa `trampa.pdf` (HTML 200) → exit 1 sin guardar PDF, export posts/types + verify, freno de export (`--max 2000` → exit 3 con 20 solicitudes estimadas) |
| Suite R `test_wp_api.R` | **`ok`, exit 0** (~90 verificaciones): mismas superficies de registro/firmas/descarga/export/verify/CLI con sesiones falsas, incluida redirección de colección como error y colección objeto envuelta |
| Python público SYMAGA | `media --mime pdf` total 5443; `--mime jpg` total 4375; download PDF (ID 49177, `documentos/2024/10/`) y JPG (ID 73369, `imagenes/2026/09/`) exit 0; `export posts` 5 de 165 con `--campos` exit 0; `verify` 3/3 |
| R público SYMAGA | `media --mime pdf --max 2` total 5443 (coincide con Python); download JPG exit 0; `export posts` y `export categories` exit 0; `verify` 2/2 |
| Convergencia Python↔R | `export posts` con idénticos `--campos` ejecutado por ambos CLIs en el mismo directorio: **una sola fila** `export:wp/v2/posts#<huella>` y un solo archivo `json/wp-v2-posts-<huella>.json`; `verify` cruzado de R sobre el manifiesto de Python: 3/3 |

Manifiestos de esta corrida: `validation/datos/smoke-v3/manifest.csv` (Python+R combinados, 3 filas válidas) y `validation/datos/smoke-v3-r/manifest.csv` (R: imagen + export de categorías). Artefactos regenerables ignorados por Git; no constituyen autorización de redistribución del material.

### Fallos intermedios corregidos durante esta revisión

- `--sleep` añadido a `media`/`preflight` (los parser perdían `--max`/`--umbral` al insertarlo).
- Export por `--id` generaba huella redundante (el ID ya está en la ruta).
- Gate de export se movió **antes** del fetch: el freno no debe gastar el servidor que quiere frenar.
- Error WP (dict con `code`) se confundía con colección; ahora lanza error.
- R: `order(NULL)` con `--campos` y sin filtros rompía `export`; huella JSON no convergía con Python → cadena canónica compartida.
- Redirección de índice same-origin faltante en R (`followlocation=0` + seguimiento manual); colecciones 3xx ahora son error explícito.

## Límites de la evidencia

- Sin credenciales ni staging autorizado: lectura privada, permisos de cuenta y operaciones de escritura **no ejecutados** (los CLI no autentican por diseño).
- Los fixtures HTTP locales no son instalaciones WordPress reales ni cubren todos los plugins; las firmas mágicas detectan tipo/HTML, no validez completa ni seguridad del contenido.
- `pypdf` ausente en esta corrida: `paginas` queda vacío en el manifiesto (verificado en R con `pdftools`).
- Las sesiones de interpretación de agentes (Claude/OpenCode) pertenecen a la revisión anterior; no se repitieron aquí. La evaluación textual previa sigue aplicando al núcleo de instrucciones, que mantiene activación, frenos y confirmaciones.
- R requiere invocación por ruta absoluta en esta máquina; el locale degradó acentos en consola (el manifiesto en disco conserva UTF-8).

## Cómo reproducir

Desde la raíz del repositorio, con Python 3.10+ (`pip install -r wp-api/assets/requirements.txt`) y R 4.4+:

```sh
python -m unittest discover -s wp-api/assets -p test_wp_api.py -v
python wp-api/validation/test_scenarios.py
Rscript wp-api/assets/test_wp_api.R
```

Flujos públicos acotados en el README de la skill (`--sleep 0.4`, `--max 1..5`). No ejecutar ejercicios de escritura contra el sitio público.
