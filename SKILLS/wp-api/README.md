# WordPress API: referencia operativa

Para aprender instalación, invocación y prompts por agente, empezar por el [README del repositorio](../README.md). Si esta carpeta se instaló por separado, ver [adaptaciones por agente](references/plataformas.md) y pedir al agente que lea `SKILL.md`.

## Dos formas de trabajar

- **Con agente:** proporcionar URL y petición natural. La SKILL dirige descubrimiento, herramientas HTTP, autenticación cuando sea imprescindible, confirmaciones y validación. No hace falta conocer comandos.
- **Con scripts:** los CLI Python/R resuelven descubrimiento, descarga de medios **públicos de cualquier formato** y **exportación JSON** de colecciones REST. No autentican ni escriben contenido en WordPress. Para acceso privado/cambios, el agente sigue [autenticación](references/autenticacion.md) y [operaciones](references/operaciones.md).

## Requisitos opcionales

Python 3.10+, `requests`; instalar `assets/requirements.txt` para las dependencias declaradas. `truststore` integra certificados del sistema cuando está disponible; `pypdf` cuenta páginas de PDF. R 4.4+, `httr2`, `jsonlite`, `digest`; `pdftools` opcional. Elegir un lenguaje, no instalar ambos por obligación.

Desde la raíz de esta carpeta instalada:

```sh
python -m pip install -r assets/requirements.txt
python assets/wp_api.py --help
```

Desde la raíz del repositorio, anteponer `wp-api/` a las rutas. El agente resuelve las rutas respecto de la SKILL cargada, no de una ubicación global supuesta.

## Comandos públicos

| Comando | Resultado |
|---|---|
| `discover --site URL` | Descubrimiento REST y capacidades observadas |
| `robots --site URL` | Lectura de robots y evaluación de uploads y `/wp-json/` |
| `media --site URL [--mime pdf,jpg] [--search T] [--max N]` | Listado de medios de cualquier tipo; alias de extensión o MIME completo |
| `preflight --site URL [--mime ...] [--search T] [--max N]` | Cantidad seleccionada, total disponible y bytes conocidos; no descarga |
| `download --site URL [--mime ...] [--search T] [--max N] --out DIR` | Descarga multi-formato con manifiesto y freno de volumen |
| `download --site URL --url URL_ARCHIVO --out DIR` | Archivo directo de cualquier tipo, sin enumerar la biblioteca |
| `download --site URL --id ID --out DIR` | Un objeto media concreto por ID |
| `export --site URL --recurso posts [--max N] [--filtro k=v] [--campos ...] [--formato json\|ndjson] --out DIR` | Colección REST (posts, pages, media, categories, tags, users, comments, types, ... o ruta como `wc/v3/products`) a JSON/NDJSON verificado |
| `verify --out DIR` | Integridad de todos los archivos registrados |

Consultar `--help` de cada comando para otras opciones como `--per-page`, `--sleep` o `--umbral`. No inferir opciones de un comando a otro. El agente debe comprobar robots y alcance antes de descargar; el CLI no reemplaza ese juicio ni todos los controles de seguridad del agente.

Formatos cubiertos por el registro de la skill (validación por bytes mágicos y familia): documentos (pdf, doc/docx, xls/xlsx, ppt/pptx, odt/ods/odp, rtf, txt, ics), datos (json, csv, tsv, xml), imágenes (jpg, png, gif, webp, avif, heic, bmp, tiff, ico, svg, psd), audio (mp3, m4a, ogg, wav, flac, aac, mka, mid...), video (mp4, mov, avi, wmv, mkv, webm, flv, mpeg, 3gp...), comprimidos (zip, gz, tar, rar, 7z) y otros (swf, exe, binarios). Cada archivo cae en `datos/<familia>/<AAAA>/<MM>/` y las exportaciones en `datos/json/`.

## Ejercicio público acotado

Desde la raíz de esta carpeta:

```sh
python assets/wp_api.py discover --site https://symaga.com
python assets/wp_api.py robots --site https://symaga.com
python assets/wp_api.py media --site https://symaga.com --search "Silos granja Distribucion pienso" --mime pdf --max 3
python assets/wp_api.py preflight --site https://symaga.com --search "Silos granja Distribucion pienso" --mime pdf --max 1
python assets/wp_api.py download --site https://symaga.com --search "Silos granja Distribucion pienso" --mime pdf --max 1 --out datos
python assets/wp_api.py media --site https://symaga.com --mime jpg --max 3
python assets/wp_api.py export --site https://symaga.com --recurso posts --max 5 --campos id,date,slug,title,link --out datos
python assets/wp_api.py verify --out datos
```

Para R, usar `Rscript assets/wp_api.R` en lugar de `python assets/wp_api.py`. En Windows, si R no está en PATH, usar la ruta real de `Rscript.exe`. No desactivar TLS para resolver certificados.

### Confirmación de volumen

Más de cinco archivos: `download` exige `--confirmo-bajar N` y, sin ella, termina con código 3 sin descargar el lote. `N` es el `a_descargar` del preflight con los **mismos filtros y máximo**, no necesariamente el máximo pedido. `export` aplica el mismo freno sobre las **solicitudes estimadas** (`ceiling(max/per_page)`): exportar 5.000 entradas a razón de 100 por página son 50 peticiones y pide `--confirmo-bajar 50`. No copiar un número histórico. El agente muestra cantidad/tamaño o alcance, obtiene consentimiento y agrega la opción; no cambia el umbral para evitar la conversación.

### Salida e integridad

`datos/manifest.csv` conserva sitio, ID, título, URL, archivo, bytes, SHA-256, páginas si es PDF y estado. Los archivos se guardan bajo `datos/<familia>/<AAAA>/<MM>/` y las exportaciones bajo `datos/json/`. Estados: `descargado`, `reutilizado`, `exportado` (los manifiestos históricos con `descargado_pdf`/`reutilizado_pdf` siguen verificándose). Verificar también si hubo errores parciales: un manifiesto no significa que todos los archivos fueran descargados.

Reejecutar puede reutilizar archivos con hash local coincidente. Eso verifica integridad local, no frescura remota ni seguridad del archivo. [Detalles de descarga y exportación](references/descarga.md).

## Diagnóstico breve

- 404/HTML en `/wp-json/`: buscar raíz anunciada y `rest_route`; no concluir ausencia de API.
- 401/403: diferenciar autenticación, permisos y WAF; estos scripts no son un cliente de contenido privado.
- Error de red/TLS: informar el error real; no inventar resultados vacíos.
- `tipo_inesperado`/`invalido`: no conservar HTML disfrazado del formato pedido ni abrir archivos dudosos.
- Export de recurso inexistente: la API responde 404 JSON; corregir el recurso, no repetir igual.
- Robots complejo o ruta CDN: revisar origen y ruta reales con herramienta adecuada; el parser del CLI es limitado.

## Validación y recursos

```sh
python -m unittest discover -s assets -p test_wp_api.py -v
python validation/test_scenarios.py
Rscript assets/test_wp_api.R
```

- [Evidencia actual](validation/REVISION.md), [histórica](validation/RESULTADOS.md), [escenarios](validation/ESCENARIOS.md).
- [Investigación y auditoría](validation/INVESTIGACION.md).
- [REST](references/rest-api.md), [descarga y exportación](references/descarga.md), [ética](references/etica-legal.md), [plataformas](references/plataformas.md).

Los fixtures locales no equivalen a instalaciones WordPress reales; las pruebas de interpretación no prueban autenticación ni escritura end-to-end. Cada informe explicita qué se ejecutó.
