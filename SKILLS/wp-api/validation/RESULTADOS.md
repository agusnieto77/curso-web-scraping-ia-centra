# WordPress API + descarga de PDF · Resultado de la prueba

> Evidencia histórica conservada del ejercicio original. Sus versiones, conteos y formatos de salida no describen necesariamente la revisión actual. Para las pruebas nuevas, correcciones y límites, leer [REVISION.md](REVISION.md).

**Resultado:** el flujo completo funciono end-to-end contra `https://symaga.com`. Se descubrio la API REST, se localizo el PDF del caso pedido por la API, se descargo y valido desde Python y desde R, y ambas implementaciones produjeron **bytes identicos** (`sha256` coincidente). La reejecucion reutiliza por hash sin volver a descargar.

Caso testigo (URL pedida): `https://symaga.com/wp-content/uploads/2024/10/Silos-granja-y-Distribucion-de-pienso-Catalogo-SYMAGA-v2.pdf`

## Que se ejecuto

| Paso | Comando | Resultado |
|---|---|---|
| Descubrir | `discover --site https://symaga.com` | HTTP 200; `wp/v2` activo; `media`/`posts`/`pages` disponibles |
| robots.txt | `robots --site https://symaga.com` | `User-agent: *` / `Disallow:` → `permite_uploads: true` |
| Buscar por titulo | `pdfs --search "Silos granja Distribucion pienso"` | 1 resultado: media `id=43887` |
| Descargar (Python) | `download --search ... --max 1` | `descargado_pdf`, 10.373.654 bytes, 8 paginas |
| Descargar (R) | idem | mismos bytes y hash |
| Descarga por URL | `download --url <pdf>` (Python y R) | mismas 10.373.654 bytes |
| Reejecutar | `download` dos veces | `reutilizado_pdf`, **sin** peticion del PDF |
| Verificar | `verify --out <dir>` | `validas: 1` (Python y R) |
| Sitio sin WordPress | `discover --site https://example.com` | falla limpio: `error: http`, status 404, exit 2 |

## Evidencia de integridad

Los tres archivos descargados por vias distintas (Python por busqueda, Python por URL, R por busqueda) tienen el mismo tamano y el mismo hash:

| Origen | Bytes | SHA-256 |
|---|---|---|
| `datos/py/pdf/2024/10/43887-...pdf` | 10.373.654 | `e81b012644283e78f4dd69a04f29bb6bc65d6360abdbe456e0b1d98823ece734` |
| `datos/r/pdf/2024/10/43887-...pdf` | 10.373.654 | `e81b012644283e78f4dd69a04f29bb6bc65d6360abdbe456e0b1d98823ece734` |
| `datos/py-url/pdf/2024/10/Silos-...pdf` | 10.373.654 | `e81b012644283e78f4dd69a04f29bb6bc65d6360abdbe456e0b1d98823ece734` |

El `content-length` de la cabecera `HEAD` (`10.373.654`) coincide con el archivo en disco y con `media_details.filesize` de la API. Los 5 primeros bytes son `%PDF-1.4`. Conteo de paginas: **8** (pypdf en Python, pdftools en R).

## Datos del objeto media (respuesta de la API)

```json
{
  "id": 43887,
  "slug": "silos-granja-y-distribucion-de-pienso-catalogo-symaga-v2",
  "title": { "rendered": "Silos granja y Distribución de pienso Catálogo SYMAGA v2" },
  "mime_type": "application/pdf",
  "date": "2026-07-13T12:39:16",
  "source_url": "https://www.symaga.com/wp-content/uploads/2024/10/Silos-granja-y-Distribucion-de-pienso-Catalogo-SYMAGA-v2.pdf"
}
```

Notas observadas:

- El sitio responde igual desde `symaga.com` y `www.symaga.com`; la API devuelve `source_url` con `www`.
- La URL de ejemplo del enunciado (HTTP) funciona; el guardado de bytes es identico.
- El stack del sitio incluye Yoast, WPML, Elementor y varios plugins mas (27 namespaces), y `wp/v2` sigue expuesto.
- La biblioteca de medios declara **5.443** PDF (`X-WP-Total`), aunque parte de los listados son fichas tecnicas. Bajar todo no es el objetivo de la skill.

## Freno de volumen: preflight + confirmacion

Agregado despues de la primera prueba, a pedido. Separado en dos partes:

- **`preflight`** (comando nuevo, no descarga): informa `total_disponible` (todo lo que matchea), `a_descargar` (lo que permite el `--max`) y `bytes_conocidos` (suma de `media_details.filesize` que la API ya devuelve).
- **Freno**: si `a_descargar > --umbral` (5 por defecto), `download` **no baja nada** y sale con **codigo 3**, pidiendo repetir el numero exacto con `--confirmo-bajar N`.

Verificado contra el sitio real:

| Prueba | Comando | Resultado |
|---|---|---|
| Preflight de biblioteca | `preflight --site https://symaga.com --max 10` | `total_disponible: 5443`, `a_descargar: 10`, `bytes_conocidos: 3.981.697` (~3,98 MB) |
| Preflight de la busqueda | `preflight --search "Silos granja..." --max 1` | `total_disponible: 1`, `a_descargar: 1`, `requiere_confirmacion: false` |
| Freno (Python) | `download --url <pdf> --umbral 0` | **exit 3**, `requiere_confirmacion`, **0 archivos** en disco |
| Freno (R) | `download --search "..." --max 1 --umbral 0` | **exit 3**, mismos datos |
| Numero equivocado | `--umbral 0 --confirmo-bajar 7` (con 1 material) | **exit 3** |
| Confirmado (Python) | `--umbral 0 --confirmo-bajar 1` | exit 0, 1 PDF + manifiesto |
| Confirmado (R) | `--umbral 0 --confirmo-bajar 1` | exit 0, 1 PDF + manifiesto |
| Sin freno por defecto | `download --search "..." --max 1` (umbral 5) | pasa sin ceremonia (1 ≤ 5) |

Esto **no** replica el freno institucional de la clase 1. Alla la puerta era un acuerdo real con Prensa Historica; aca no hay gatekeeper, asi que el freno es un **contrato de atencion**: te obliga a escribir el numero que viste. Fingir una autorizacion que nadie puede otorgar seria ceremonia vacia.

## Suites de pruebas (sin red)

- **Python: 23 pruebas, todas aprobadas.** `python -m unittest discover -s SKILLS/wordpress-api-pdf/assets -p test_wp_api.py`
- **R: suite completa con `ok`.** `Rscript SKILLS/wordpress-api-pdf/assets/test_wp_api.R`

Cubren: normalizacion de URL, `robots.txt` (incluido el bloque de un agente especifico), validacion de PDF (valido, HTML con extension `.pdf`, vacio, ausente, hash alterado), clave de identidad por `id`, fusion del manifiesto sin duplicados y preservando otros sitios, round-trip del CSV con acentos, mapeo de item de API a registro, parseo de argumentos, conteo de paginas, **logica del freno** (bajo el umbral, en el umbral, sobre el umbral, numero exacto, numero equivocado, valor basura, umbral 0), **calculo del preflight** (totales, bytes, faltantes) y un caso de integracion con sesion HTTP falsa que comprueba la **reutilizacion** (la segunda corrida no pide el PDF), que **el freno no intenta descargar** y que **confirmando si descarga**.

## Fallos encontrados y corregidos

1. **Reutilizacion rota por tipo de dato.** `cmd_download` comparaba el `id` entero que devuelve la API contra el `id` texto leido del CSV, por lo que nunca encontraba el hash previo y **volvia a descargar**. Se normalizo la clave a texto en ambos lados. Detectado al revisar el resumen de la segunda corrida (`descargado_pdf` en lugar de `reutilizado_pdf`). Regresion agregada en `TestDescargaComoComando`.
2. **Conteo de paginas erroneo en R.** Se usaba `length(pdf_info(ruta)$pages)`, que devuelve siempre `1`; el valor real es `pdf_info(ruta)$pages`. Reportaba 1 pagina en vez de 8. Regresion agregada en la suite R (`cuenta_paginas_reales`).
3. **Nombre de archivo duplicado con `--url`.** Al usar la URL directa, el `id` y el `slug` salian del mismo nombre y el archivo quedaba `x/x-x.pdf`. Se evita el duplicado cuando coinciden.

El primer fallo (reutilizacion) es el tipico error de comparar enteros y texto al pasar por CSV; solo aparecio por ejecutar la **segunda** corrida y leer el resultado.

## Limites de esta prueba (lo que NO queda demostrado)

- Se probo **un sitio** (WordPress con Yoast/WPML/Elementor). Otros stacks pueden cambiar `rest_base` o bloquear `/wp-json/`.
- Se probo **un PDF** y **una busqueda**; no se valido la paginacion sobre miles de resultados ni un muestreo de 100+.
- No se probo contenido autenticado (Application Passwords): el flujo publico no lo necesita.
- `paginas` depende de `pypdf`/`pdftools`: si no estan instalados, la columna queda vacia (no rompe la descarga).
- La licencia del catalogo **no** fue verificada; la columna `licencia` del manifiesto queda vacia a proposito.

## Archivos de evidencia

Guardados en `validation/datos/` (carpeta ignorada por git; los PDF pesan ~10 MB):

| Archivo | Contenido |
|---|---|
| `evidencia-discover.py.json`, `evidencia-discover.R.json` | Indice del sitio y robots, desde cada lenguaje |
| `evidencia-robots.py.json` | Lectura de robots.txt |
| `evidencia-pdfs.py.json` | Listado del media por busqueda |
| `evidencia-download.py.json`, `evidencia-download.R.json` | Resumen de descarga |
| `evidencia-redownload.py.json`, `evidencia-redownload.R.json` | Prueba de reutilizacion |
| `evidencia-verify.py.json`, `evidencia-verify.R.json`, `evidencia-verify-cruzada.R.json` | Verificacion de integridad (incluye R validando la salida de Python) |
| `evidencia-url.py.json`, `evidencia-url.R.json` | Descarga por URL directa |
| `evidencia-no-wp.py.json` | Falla controlada en un sitio sin WordPress |
| `evidencia-preflight.py.json` | Preflight de la biblioteca completa (5443 disponibles) |
| `evidencia-gate-r.json` | Freno confirmado en R con el numero exacto |

## Como reproducir

```powershell
python -m pip install -r SKILLS/wordpress-api-pdf/assets/requirements.txt

$env:LC_ALL = "en_US.UTF-8"; $env:LANG = "en_US.UTF-8"

python SKILLS/wordpress-api-pdf/assets/wp_api.py discover --site https://symaga.com
python SKILLS/wordpress-api-pdf/assets/wp_api.py preflight --site https://symaga.com --max 10
python SKILLS/wordpress-api-pdf/assets/wp_api.py download --site https://symaga.com --search "Silos granja Distribucion pienso" --max 1 --out SKILLS/wordpress-api-pdf/validation/datos
python SKILLS/wordpress-api-pdf/assets/wp_api.py verify   --out SKILLS/wordpress-api-pdf/validation/datos

& "C:\Program Files\R\R-4.6.1\bin\Rscript.exe" SKILLS/wordpress-api-pdf/assets/wp_api.R download --site https://symaga.com --search "Silos granja Distribucion pienso" --max 1 --out SKILLS/wordpress-api-pdf/validation/datos/r
& "C:\Program Files\R\R-4.6.1\bin\Rscript.exe" SKILLS/wordpress-api-pdf/assets/wp_api.R verify   --out SKILLS/wordpress-api-pdf/validation/datos/r
```

## Entorno observado

- Python 3.13.0 con `requests`, `truststore` y `pypdf`; TLS verificado contra el almacen de certificados de Windows (`truststore`), sin desactivar la verificacion.
- R 4.6.1 con `httr2`, `jsonlite`, `digest` y `pdftools`.
- Windows 10 (PowerShell 5.1). Para guardar JSON legible: `| Out-File -Encoding utf8` (la redireccion `>` de PS 5.1 usa UTF-16).
