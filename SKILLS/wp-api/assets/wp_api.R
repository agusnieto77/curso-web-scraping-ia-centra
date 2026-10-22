#!/usr/bin/env Rscript
# Cliente minimo para la API REST de WordPress: descarga verificada de medios
# de cualquier formato y exportacion JSON de colecciones REST.
#
# Uso (desde la raiz de la skill):
#   Rscript wp_api.R discover --site https://ejemplo.com
#   Rscript wp_api.R robots   --site https://ejemplo.com
#   Rscript wp_api.R media    --site https://ejemplo.com --mime pdf --search "catalogo" --max 5
#   Rscript wp_api.R download --site https://ejemplo.com --mime pdf,jpg --max 1 --out datos
#   Rscript wp_api.R download --site https://ejemplo.com --url https://.../archivo.ext --out datos
#   Rscript wp_api.R download --site https://ejemplo.com --id 123 --out datos
#   Rscript wp_api.R export   --site https://ejemplo.com --recurso posts --max 100 --out datos
#   Rscript wp_api.R verify   --out datos
#
# Solo usa endpoints publicos de lectura (GET). No envia credenciales.

suppressPackageStartupMessages({
  library(httr2)
  library(jsonlite)
  library(digest)
})

wp_user_agent <- function() {
  paste0("curso-web-scraping-ia-centra/1.0 (docencia; contacto: agusnieto77) httr2/",
         as.character(utils::packageVersion("httr2")))
}

wp_timeout <- 30
wp_pausa <- 1.0
wp_per_page_max <- 100L
wp_umbral_confirmacion <- 5L
wp_reintentos_max <- 2L      # solo lecturas transitorias (429/5xx/red), nunca escrituras
wp_reintento_tope_s <- 20    # Retry-After mayor: no esperar, devolver el error
wp_redirecciones_http <- c(301L, 302L, 303L, 307L, 308L)

# Estados de exito del manifiesto. Los *_pdf son de manifiestos historicos y
# siguen verificandose para no romper evidencia previa.
wp_estados_ok <- c("descargado", "reutilizado", "exportado", "descargado_pdf", "reutilizado_pdf")
wp_estados_fallo <- c("error_http", "tipo_inesperado", "invalido", "error_url")

wp_manifest_cols <- c(
  "sitio", "id", "titulo", "slug", "fecha_media", "mime_type", "url_media",
  "url_api", "archivo", "bytes", "sha256", "paginas", "estado", "motivo",
  "licencia", "capturado_en_utc"
)

# --------------------------------------------------------------------------- #
# Registro de formatos: MIME -> (extensiones, familia, firma de bytes)
# Cubre los tipos que WordPress acepta en la biblioteca de medios
# (wp_get_mime_types + get_allowed_mime_types) y textos/enlaces habituales.
# --------------------------------------------------------------------------- #
wp_registro_mime <- list(
  # Documentos
  list("application/pdf", c("pdf"), "documentos", "pdf"),
  list("application/x-pdf", c("pdf"), "documentos", "pdf"),
  list("application/msword", c("doc"), "documentos", "ole"),
  list("application/vnd.msword", c("doc"), "documentos", "ole"),
  list("application/vnd.openxmlformats-officedocument.wordprocessingml.document", c("docx"), "documentos", "zip"),
  list("application/vnd.ms-excel", c("xls"), "documentos", "ole"),
  list("application/vnd.ms-powerpoint", c("ppt"), "documentos", "ole"),
  list("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", c("xlsx"), "documentos", "zip"),
  list("application/vnd.openxmlformats-officedocument.presentationml.presentation", c("pptx"), "documentos", "zip"),
  list("application/vnd.oasis.opendocument.text", c("odt"), "documentos", "zip"),
  list("application/vnd.oasis.opendocument.spreadsheet", c("ods"), "documentos", "zip"),
  list("application/vnd.oasis.opendocument.presentation", c("odp"), "documentos", "zip"),
  list("application/rtf", c("rtf"), "documentos", "rtf"),
  list("text/plain", c("txt", "asc", "c", "cc", "h", "srt", "md"), "documentos", "texto"),
  list("text/calendar", c("ics"), "documentos", "ics"),
  # Datos
  list("application/json", c("json"), "datos", "json"),
  list("text/csv", c("csv"), "datos", "texto"),
  list("text/tab-separated-values", c("tsv"), "datos", "texto"),
  list("application/xml", c("xml"), "datos", "xml"),
  list("text/xml", c("xml"), "datos", "xml"),
  # Imagenes
  list("image/jpeg", c("jpg", "jpeg", "jpe"), "imagenes", "jpg"),
  list("image/pjpeg", c("jpg"), "imagenes", "jpg"),
  list("image/png", c("png"), "imagenes", "png"),
  list("image/gif", c("gif"), "imagenes", "gif"),
  list("image/webp", c("webp"), "imagenes", "webp"),
  list("image/avif", c("avif"), "imagenes", "ftyp"),
  list("image/heic", c("heic"), "imagenes", "ftyp"),
  list("image/bmp", c("bmp"), "imagenes", "bmp"),
  list("image/tiff", c("tiff", "tif"), "imagenes", "tiff"),
  list("image/x-icon", c("ico"), "imagenes", "ico"),
  list("image/svg+xml", c("svg"), "imagenes", "svg"),
  list("image/vnd.adobe.photoshop", c("psd"), "imagenes", "psd"),
  # Audio
  list("audio/mpeg", c("mp3", "m4a", "m4b"), "audio", "mp3"),
  list("audio/mp4", c("m4a"), "audio", "ftyp"),
  list("audio/x-m4a", c("m4a"), "audio", "ftyp"),
  list("audio/ogg", c("ogg", "oga"), "audio", "ogg"),
  list("audio/wav", c("wav"), "audio", "wav"),
  list("audio/x-wav", c("wav"), "audio", "wav"),
  list("audio/wave", c("wav"), "audio", "wav"),
  list("audio/flac", c("flac"), "audio", "flac"),
  list("audio/aac", c("aac"), "audio", "aac"),
  list("audio/x-matroska", c("mka"), "audio", "ebml"),
  list("audio/midi", c("mid", "midi"), "audio", "mid"),
  list("audio/x-realaudio", c("ra", "ram"), "audio", NA),
  list("audio/x-ms-wma", c("wma"), "audio", "asf"),
  # Video
  list("video/mp4", c("mp4", "m4v"), "video", "ftyp"),
  list("video/x-m4v", c("m4v"), "video", "ftyp"),
  list("video/quicktime", c("mov", "qt"), "video", "ftyp"),
  list("video/x-msvideo", c("avi"), "video", "avi"),
  list("video/x-ms-wmv", c("wmv"), "video", "asf"),
  list("video/x-matroska", c("mkv"), "video", "ebml"),
  list("video/webm", c("webm"), "video", "ebml"),
  list("video/x-flv", c("flv"), "video", "flv"),
  list("video/mpeg", c("mpeg", "mpg", "mpe"), "video", "mpeg"),
  list("video/3gpp", c("3gp"), "video", "ftyp"),
  list("video/3gpp2", c("3g2"), "video", "ftyp"),
  # Comprimidos
  list("application/zip", c("zip"), "comprimidos", "zip"),
  list("application/x-zip-compressed", c("zip"), "comprimidos", "zip"),
  list("application/x-gzip", c("gz", "gzip"), "comprimidos", "gzip"),
  list("application/gzip", c("gz"), "comprimidos", "gzip"),
  list("application/x-tar", c("tar"), "comprimidos", "tar"),
  list("application/x-rar-compressed", c("rar"), "comprimidos", "rar"),
  list("application/x-7z-compressed", c("7z"), "comprimidos", "7z"),
  # Otros
  list("application/x-shockwave-flash", c("swf"), "otros", "swf"),
  list("application/x-msdownload", c("exe"), "otros", "exe"),
  list("application/octet-stream", c("bin"), "otros", NA)
)

wp_alias_mime <- list(
  "x-pdf" = "pdf", pjpeg = "jpg", jpeg = "jpg", jpe = "jpg", tif = "tiff",
  oga = "ogg", m4v = "mp4", qt = "mov", mpg = "mpeg", mpe = "mpeg", gzip = "gz"
)

wp_por_mime <- stats::setNames(wp_registro_mime, vapply(wp_registro_mime, `[[`, "", 1L))
wp_ext_a_mime <- list()
for (reg in wp_registro_mime) {
  for (ext in reg[[2L]]) if (is.null(wp_ext_a_mime[[ext]])) wp_ext_a_mime[[ext]] <- reg[[1L]]
}

wp_familias <- c("documentos", "datos", "imagenes", "audio", "video", "comprimidos", "otros")

wp_recursos_export <- list(
  posts = "wp/v2/posts", pages = "wp/v2/pages", media = "wp/v2/media",
  categories = "wp/v2/categories", tags = "wp/v2/tags", users = "wp/v2/users",
  comments = "wp/v2/comments", types = "wp/v2/types", statuses = "wp/v2/statuses",
  taxonomies = "wp/v2/taxonomies", search = "wp/v2/search", settings = "wp/v2/settings"
)

# --------------------------------------------------------------------------- #
# Utilidades puras
# --------------------------------------------------------------------------- #
`%||%` <- function(a, b) if (is.null(a) || (length(a) == 1 && is.na(a))) b else a

wp_normalizar_sitio <- function(url) {
  if (is.null(url) || !nzchar(url)) stop("URL de sitio vacia", call. = FALSE)
  texto <- trimws(url)
  if (grepl("^[a-zA-Z][a-zA-Z0-9+.-]*://", texto) && !grepl("^https?://", texto, ignore.case = TRUE)) {
    stop(sprintf("Esquema no permitido en la URL del sitio: %s", url), call. = FALSE)
  }
  if (!grepl("^https?://", texto, ignore.case = TRUE)) texto <- paste0("https://", texto)
  partes <- regmatches(texto, regexec("^(https?://[^/?#]+)(/[^?#]*)?", texto))[[1]]
  if (length(partes) < 2) stop(sprintf("URL de sitio invalida: %s", url), call. = FALSE)
  base <- partes[2]
  if (grepl("@", base, fixed = TRUE)) stop("URL de sitio no debe incluir userinfo", call. = FALSE)
  if (length(partes) >= 3 && nzchar(partes[3])) {
    ruta <- sub("/+$", "", partes[3])
    if (nzchar(ruta)) base <- paste0(base, ruta)
  }
  base
}

wp_origen_sitio <- function(url) {
  base <- wp_normalizar_sitio(url)
  partes <- regmatches(base, regexec("^(https?://[^/]+)", base))[[1]]
  if (length(partes) < 2) base else partes[2]
}

wp_api_base <- function(site) paste0(sub("/+$", "", wp_normalizar_sitio(site)), "/wp-json")

wp_ruta_media <- function(api_base, rest_base = "media") {
  paste0(sub("/+$", "", api_base), "/wp/v2/", rest_base)
}

wp_base_indice_api <- function(indice_url) {
  if (is.null(indice_url) || !nzchar(indice_url)) return(NULL)
  sub("/+$", "", indice_url)
}

wp_ruta_coleccion <- function(api_base, ruta_recurso) {
  # Coleccion REST arbitraria ('wp/v2/posts', 'wc/v3/products') sobre la raiz
  # descubierta, respetando rest_route. Sin '..' ni caracteres raros.
  ruta <- gsub("^/+|/+$", "", ruta_recurso)
  if (!nzchar(ruta)) stop("Ruta de recurso vacia", call. = FALSE)
  if (!grepl("^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$", ruta)) {
    stop(sprintf("Ruta de recurso invalida: %s", ruta_recurso), call. = FALSE)
  }
  if (any(strsplit(ruta, "/", fixed = TRUE)[[1]] == "..")) {
    stop(sprintf("Ruta de recurso invalida: %s", ruta_recurso), call. = FALSE)
  }
  base <- sub("/+$", "", api_base)
  if (grepl("[?&]rest_route=", base)) {
    # <base>/?rest_route=/  ->  <base>/?rest_route=/wp/v2/x
    partes <- strsplit(base, "?", fixed = TRUE)[[1]]
    query <- if (length(partes) >= 2) partes[[2]] else ""
    pares <- strsplit(query, "&", fixed = TRUE)[[1]]
    pares <- pares[pares != ""]
    pares <- vapply(pares, function(p) {
      if (startsWith(p, "rest_route=")) "rest_route=PLACEHOLDER" else p
    }, character(1), USE.NAMES = FALSE)
    ruta_q <- utils::URLencode(paste0("/", ruta), reserved = TRUE)
    pares <- sub("rest_route=PLACEHOLDER", paste0("rest_route=", ruta_q), pares)
    paste0(partes[[1]], "?", paste(pares, collapse = "&"))
  } else if (grepl("/wp-json$", base)) {
    paste0(base, "/", ruta)
  } else {
    paste0(base, "/wp-json/", ruta)
  }
}

wp_indice_api_valido <- function(cuerpo) {
  is.list(cuerpo) && !is.null(cuerpo$routes) && length(cuerpo$routes) > 0 &&
    !is.null(cuerpo$namespaces)
}

wp_extraer_link_api <- function(link_header, sitio) {
  if (is.null(link_header) || !nzchar(link_header)) return(NULL)
  partes <- regmatches(link_header, regexec("<([^>]+)>;\\s*rel=\"https://api\\.w\\.org/\"", link_header, perl = TRUE))[[1]]
  if (length(partes) < 2) return(NULL)
  enlace <- trimws(partes[2])
  destino <- httr2::url_modify_relative(sitio, enlace)
  if (!grepl("^https?://", destino, ignore.case = TRUE)) stop("Link api.w.org debe usar esquema HTTP(S)", call. = FALSE)
  partes_url <- httr2::url_parse(destino)
  if (!is.null(partes_url$username) || !is.null(partes_url$password)) {
    stop("Link api.w.org no debe incluir userinfo", call. = FALSE)
  }
  if (!identical(wp_origen_sitio(destino), wp_origen_sitio(sitio))) {
    stop("Link api.w.org apunta a otro origen", call. = FALSE)
  }
  destino
}

wp_describir_error_descubrimiento <- function(info) {
  sitio <- info$site %||% ""
  indice <- info$indice_url %||% sitio
  if (identical(info$error, "http_401") || identical(info$error, "http_403")) {
    return(sprintf("API REST restringida (%s) en %s", info$error, indice))
  }
  if (identical(info$error, "red")) {
    detalle <- info$detalle %||% "sin detalle"
    return(sprintf("Error de red al descubrir la API en %s: %s", indice, detalle))
  }
  if (identical(info$error, "indice_invalido")) {
    return(sprintf("Indice REST invalido en %s (status %s, content-type %s)",
                   indice, info$status %||% "?", info$content_type %||% "desconocido"))
  }
  if (identical(info$error, "link_invalido")) {
    return(sprintf("Link api.w.org invalido en %s: %s", indice, info$detalle %||% "sin detalle"))
  }
  sprintf("No se encontro una API REST valida en %s (probo /wp-json/, ?rest_route=/ y Link api.w.org)", sitio)
}

wp_sanitizar_nombre <- function(texto, max_len = 80L) {
  texto <- if (is.null(texto)) "" else texto
  limpio <- gsub("[^[:alnum:]_.-]+", "-", texto, perl = TRUE)
  limpio <- gsub("[[:space:]_]+", "-", limpio, perl = TRUE)
  limpio <- gsub("^[-.]+|[-.]+$", "", limpio)
  limpio <- gsub("-{2,}", "-", limpio)
  if (!nzchar(limpio)) limpio <- "sin-titulo"
  substr(limpio, 1, max_len)
}

wp_sha256 <- function(ruta) digest::digest(file = ruta, algo = "sha256", serialize = FALSE)

wp_normalizar_mime <- function(mime) {
  if (is.null(mime) || !nzchar(mime)) return(NA_character_)
  base <- tolower(trimws(strsplit(as.character(mime), ";", fixed = TRUE)[[1]][1]))
  if (!nzchar(base)) NA_character_ else base
}

wp_descripcion_mime <- function(mime) {
  base <- wp_normalizar_mime(mime)
  if (is.na(base)) return(NULL)
  reg <- wp_por_mime[[base]]
  if (!is.null(reg)) return(reg)
  alias <- wp_alias_mime[[sub("^.+/", "", base)]]
  if (!is.null(alias)) wp_por_mime[[alias]] else NULL
}

wp_familia_de_mime <- function(mime) {
  reg <- wp_descripcion_mime(mime)
  if (!is.null(reg)) return(reg[[3L]])
  base <- wp_normalizar_mime(mime)
  if (is.na(base)) return("otros")
  if (startsWith(base, "image/")) "imagenes"
  else if (startsWith(base, "audio/")) "audio"
  else if (startsWith(base, "video/")) "video"
  else "otros"
}

wp_firma_de_mime <- function(mime) {
  reg <- wp_descripcion_mime(mime)
  if (is.null(reg)) NA_character_ else reg[[4L]]
}

wp_extension_de_url <- function(url) {
  if (is.null(url) || !nzchar(url)) return(NA_character_)
  trozos <- strsplit(sub("[?#].*$", "", url), "/", fixed = TRUE)[[1]]
  ultimo <- trozos[length(trozos)]
  m <- regmatches(ultimo, regexec("([A-Za-z0-9]+)$", ultimo))
  if (length(m[[1]]) >= 2) tolower(m[[1]][2]) else NA_character_
}

wp_resolver_destino <- function(mime, url_media) {
  # (extension, familia, firma) para guardar. Prioriza el MIME informado por la
  # API; si falta, deduce desde la extension de la URL.
  ext_url <- wp_extension_de_url(url_media)
  reg <- wp_descripcion_mime(mime)
  if (!is.null(reg)) {
    ext <- if (!is.na(ext_url) && ext_url %in% reg[[2L]]) ext_url else reg[[2L]][1]
    return(list(ext = ext, familia = reg[[3L]], firma = reg[[4L]]))
  }
  if (!is.na(ext_url) && !is.null(wp_ext_a_mime[[ext_url]])) {
    return(wp_resolver_destino(wp_ext_a_mime[[ext_url]], url_media))
  }
  ext <- if (is.na(ext_url)) "bin" else ext_url
  list(ext = ext, familia = wp_familia_de_mime(mime), firma = NA_character_)
}

wp_resolver_mimes <- function(texto) {
  # 'pdf,jpg' o 'application/pdf,image/jpeg' -> lista de MIMEs.
  # NULL o 'todos' significa sin filtro. Token desconocido: error (no filtrar
  # de mas ni de menos en el servidor sin darnos cuenta).
  if (is.null(texto) || !nzchar(texto)) return(NULL)
  tokens <- tolower(trimws(strsplit(texto, "[,[:space:]]+", perl = TRUE)[[1]]))
  tokens <- tokens[nzchar(tokens)]
  if (!length(tokens) || any(tokens %in% c("*", "todos", "all"))) return(NULL)
  mimes <- character(0)
  for (token in tokens) {
    if (!is.null(wp_ext_a_mime[[token]])) {
      mime <- wp_ext_a_mime[[token]]
    } else if (!is.null(wp_por_mime[[token]])) {
      mime <- token
    } else {
      stop(sprintf("MIME o alias desconocido: '%s'. Alias conocidos: %s", token,
                   paste(sort(names(wp_ext_a_mime)), collapse = ", ")), call. = FALSE)
    }
    if (!(mime %in% mimes)) mimes <- c(mimes, mime)
  }
  mimes
}

wp_tipo_contenido_aceptable <- function(content_type, mime_esperado) {
  base <- wp_normalizar_mime(content_type)
  if (is.na(base)) return(TRUE)  # servidor sin content-type: firma de bytes decide
  if (base %in% c("text/html", "application/xhtml+xml")) return(FALSE)
  if (is.na(wp_normalizar_mime(mime_esperado))) return(TRUE)
  if (identical(base, wp_normalizar_mime(mime_esperado))) return(TRUE)
  if (base %in% c("application/octet-stream", "application/binary", "binary/octet-stream")) return(TRUE)
  identical(wp_familia_de_mime(base), wp_familia_de_mime(mime_esperado))
}

wp_leer_cabecera <- function(ruta, n = 64L) {
  con <- file(ruta, "rb"); on.exit(close(con), add = TRUE)
  cab <- readBin(con, "raw", n)
  if (length(cab) >= 3 && identical(cab[1:3], as.raw(c(0xEF, 0xBB, 0xBF)))) cab <- cab[-(1:3)]  # BOM UTF-8
  cab
}

wp_leer_texto <- function(ruta, limite = 4096L) {
  con <- file(ruta, "rb"); on.exit(close(con), add = TRUE)
  datos <- readBin(con, "raw", limite)
  trimws(rawToChar(datos), which = "left")
}

wp_parece_html <- function(texto) {
  inicio <- tolower(substr(texto, 1, 200))
  startsWith(inicio, "<!doctype html") || startsWith(inicio, "<html")
}

wp_verificar_texto_plano <- function(ruta) {
  if (wp_parece_html(wp_leer_texto(ruta))) return(list(valido = FALSE, motivo = "parece_html"))
  list(valido = TRUE, motivo = "ok")
}

wp_verificar_json_archivo <- function(ruta) {
  ok <- tryCatch({
    jsonlite::fromJSON(paste0(readLines(ruta, warn = FALSE, encoding = "UTF-8"), collapse = "\n"),
                       simplifyVector = FALSE)
    TRUE
  }, error = function(e) FALSE)
  if (ok) list(valido = TRUE, motivo = "ok") else list(valido = FALSE, motivo = "json_invalido")
}

wp_verificar_svg <- function(ruta) {
  texto <- wp_leer_texto(ruta, 4096L)
  if (wp_parece_html(texto)) return(list(valido = FALSE, motivo = "parece_html"))
  if (!grepl("<svg", tolower(substr(texto, 1, 4000)), fixed = TRUE)) {
    return(list(valido = FALSE, motivo = "no_es_svg"))
  }
  list(valido = TRUE, motivo = "ok")
}

wp_empieza <- function(cab, prefijo) {
  n <- length(prefijo)
  length(cab) >= n && identical(cab[seq_len(n)], prefijo)
}

wp_verificar_firma <- function(ruta, firma) {
  # (valido, motivo) segun los bytes magicos. Ninguna firma demuestra que el
  # archivo sea seguro de abrir. NA firma = formato sin firma confiable:
  # solo se rechaza HTML disfrazado.
  if (!file.exists(ruta) || dir.exists(ruta)) return(list(valido = FALSE, motivo = "archivo_ausente"))
  if (file.info(ruta)$size == 0) return(list(valido = FALSE, motivo = "archivo_vacio"))
  if (identical(firma, "json")) return(wp_verificar_json_archivo(ruta))
  if (identical(firma, "svg")) return(wp_verificar_svg(ruta))
  if (is.na(firma) || identical(firma, "texto")) return(wp_verificar_texto_plano(ruta))

  cab <- wp_leer_cabecera(ruta)
  ok <- switch(firma,
    pdf = wp_empieza(cab, charToRaw("%PDF-")),
    zip = wp_empieza(cab, as.raw(c(0x50, 0x4B, 0x03, 0x04))) ||
      wp_empieza(cab, as.raw(c(0x50, 0x4B, 0x05, 0x06))) ||
      wp_empieza(cab, as.raw(c(0x50, 0x4B, 0x07, 0x08))),
    "7z" = wp_empieza(cab, as.raw(c(0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C))),
    rar = wp_empieza(cab, as.raw(c(0x52, 0x61, 0x72, 0x21, 0x1A, 0x07))),
    gzip = wp_empieza(cab, as.raw(c(0x1F, 0x8B))),
    tar = {
      con <- file(ruta, "rb"); on.exit(close(con), add = TRUE)
      seek(con, 257)
      wp_empieza(readBin(con, "raw", 8), charToRaw("ustar"))
    },
    ole = wp_empieza(cab, as.raw(c(0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1))),
    png = wp_empieza(cab, as.raw(c(0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))),
    jpg = wp_empieza(cab, as.raw(c(0xFF, 0xD8, 0xFF))),
    gif = wp_empieza(cab, charToRaw("GIF87a")) || wp_empieza(cab, charToRaw("GIF89a")),
    webp = identical(cab[1:4], charToRaw("RIFF")) && identical(cab[5:8], charToRaw("WEBP")),
    wav = identical(cab[1:4], charToRaw("RIFF")) && identical(cab[5:8], charToRaw("WAVE")),
    avi = identical(cab[1:4], charToRaw("RIFF")) && identical(cab[5:8], charToRaw("AVI ")),
    bmp = identical(cab[1:2], charToRaw("BM")),
    ico = wp_empieza(cab, as.raw(c(0x00, 0x00, 0x01, 0x00))),
    tiff = wp_empieza(cab, as.raw(c(0x49, 0x49, 0x2A, 0x00))) ||
      wp_empieza(cab, as.raw(c(0x4D, 0x4D, 0x00, 0x2A))),
    psd = wp_empieza(cab, charToRaw("8BPS")),
    ftyp = length(cab) >= 8 && identical(cab[5:8], charToRaw("ftyp")),
    ebml = wp_empieza(cab, as.raw(c(0x1A, 0x45, 0xDF, 0xA3))),
    ogg = wp_empieza(cab, charToRaw("OggS")),
    flac = wp_empieza(cab, charToRaw("fLaC")),
    aac = wp_empieza(cab, charToRaw("ADIF")) ||
      identical(cab[1:2], as.raw(c(0xFF, 0xF1))) || identical(cab[1:2], as.raw(c(0xFF, 0xF9))),
    mid = wp_empieza(cab, charToRaw("MThd")),
    mp3 = wp_empieza(cab, charToRaw("ID3")) ||
      (length(cab) >= 2 && cab[1] == as.raw(0xFF) && (as.integer(cab[2]) %% 32L) >= 28L),
    mpeg = wp_empieza(cab, as.raw(c(0x00, 0x00, 0x01, 0xBA))) ||
      wp_empieza(cab, as.raw(c(0x00, 0x00, 0x01, 0xB3))),
    flv = wp_empieza(cab, charToRaw("FLV")),
    asf = wp_empieza(cab, as.raw(c(0x30, 0x26, 0xB2, 0x75, 0x8E, 0x66, 0xCF, 0x11))),
    swf = wp_empieza(cab, charToRaw("FWS")) || wp_empieza(cab, charToRaw("CWS")),
    exe = wp_empieza(cab, charToRaw("MZ")),
    rtf = wp_empieza(cab, charToRaw("{\\rtf")),
    ics = startsWith(toupper(rawToChar(wp_leer_cabecera(ruta, 15L))), "BEGIN:VCALENDAR"),
    xml = {
      texto <- trimws(wp_leer_texto(ruta, 64L))
      startsWith(texto, "<?xml") || startsWith(texto, "<")
    },
    # firma sin implementar: solo anti-HTML
    wp_verificar_texto_plano(ruta)$valido
  )
  if (isTRUE(ok)) list(valido = TRUE, motivo = "ok")
  else list(valido = FALSE, motivo = sprintf("firma:no_es_%s", firma))
}

wp_validar_archivo <- function(ruta, firma, expected_sha256 = NULL) {
  v <- wp_verificar_firma(ruta, firma)
  if (!isTRUE(v$valido)) return(v)
  if (!is.null(expected_sha256) && nzchar(expected_sha256)) {
    if (!identical(tolower(wp_sha256(ruta)), tolower(expected_sha256))) {
      return(list(valido = FALSE, motivo = "hash_mismatch"))
    }
  }
  v
}

wp_contar_paginas <- function(ruta) {
  if (!requireNamespace("pdftools", quietly = TRUE)) return(NA_integer_)
  tryCatch(as.integer(pdftools::pdf_info(ruta)$pages), error = function(e) NA_integer_)
}

wp_permite_robots <- function(texto, ruta, agente = "*") {
  if (is.null(texto) || !nzchar(texto)) return(TRUE)
  lineas <- strsplit(texto, "\r?\n")[[1]]
  lineas <- sub("#.*$", "", lineas)
  lineas <- trimws(lineas)
  lineas <- lineas[nzchar(lineas)]
  grupos <- list(); actuales <- character(0)
  for (linea in lineas) {
    pos <- regexpr(":", linea, fixed = TRUE)
    if (pos < 1) next
    campo <- tolower(trimws(substr(linea, 1, pos - 1)))
    valor <- trimws(substr(linea, pos + 1, nchar(linea)))
    if (campo == "user-agent") {
      actuales <- tolower(valor)
      for (a in actuales) if (is.null(grupos[[a]])) grupos[[a]] <- character(0)
    } else if (campo == "disallow" && length(actuales)) {
      for (a in actuales) grupos[[a]] <- c(grupos[[a]], valor)
    }
  }
  reglas <- grupos[[tolower(agente)]]
  if (is.null(reglas)) reglas <- grupos[["*"]]
  if (is.null(reglas)) return(TRUE)
  reglas <- reglas[nzchar(reglas)]
  if (!length(reglas)) return(TRUE)
  !any(vapply(reglas, function(r) startsWith(ruta, r), logical(1)))
}

# Freno de volumen: por encima del umbral hay que repetir el numero exacto del
# preflight. No es una autorizacion institucional, es obligar a mirar el costo.
wp_requiere_confirmacion <- function(a_descargar, umbral, confirmo = NULL) {
  if (a_descargar <= umbral) return(FALSE)
  n <- suppressWarnings(as.integer(confirmo))
  if (length(n) != 1L || is.na(n)) return(TRUE)
  n != as.integer(a_descargar)
}

wp_resumen_preflight <- function(sesion, registros, total = NULL, consulta = "") {
  tamanos <- vapply(registros, function(r) {
    v <- r$bytes_api
    if (is.null(v) || !length(v)) NA_real_ else as.numeric(v)
  }, numeric(1))
  list(
    sitio = sesion$site,
    consulta = consulta %||% "",
    total_disponible = if (is.null(total)) NULL else as.integer(total),
    a_descargar = length(registros),
    bytes_conocidos = sum(tamanos, na.rm = TRUE),
    sin_tamano = sum(is.na(tamanos)),
    muestra = lapply(utils::head(registros, 5L), function(r) {
      list(id = r$id %||% "", titulo = substr(r$titulo %||% "", 1L, 70L), bytes = r$bytes_api %||% NULL)
    })
  )
}

wp_fila_manifest <- function(reg, ...) {
  fila <- stats::setNames(as.list(rep("", length(wp_manifest_cols))), wp_manifest_cols)
  for (k in intersect(names(reg), wp_manifest_cols)) fila[[k]] <- as.character(reg[[k]] %||% "")
  extra <- list(...)
  for (k in names(extra)) if (k %in% wp_manifest_cols) fila[[k]] <- as.character(extra[[k]] %||% "")
  as.data.frame(fila, stringsAsFactors = FALSE)
}

wp_empty_manifest <- function() {
  df <- stats::setNames(as.list(rep("", length(wp_manifest_cols))), wp_manifest_cols)
  as.data.frame(df, stringsAsFactors = FALSE)[0, , drop = FALSE]
}

wp_upsert_manifest <- function(previas, nuevas) {
  safe <- function(df) if (is.null(df) || !nrow(df)) wp_empty_manifest() else df
  previas <- safe(previas); nuevas <- safe(nuevas)
  if (!nrow(previas)) return(safe(nuevas))
  if (!nrow(nuevas)) return(previas)
  todas <- rbind(previas, nuevas)
  clave <- paste(todas$sitio, todas$id, sep = "\r")
  todas[!duplicated(clave, fromLast = TRUE), , drop = FALSE]
}

wp_ahora_utc <- function() format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ")

wp_segmento_uploads <- function(url_media) {
  m <- regmatches(url_media, regexec("/uploads/([0-9]{4}/[0-9]{2})/", url_media))[[1]]
  if (length(m) >= 2) m[2] else "sin-fecha"
}

# --------------------------------------------------------------------------- #
# Cliente HTTP
# --------------------------------------------------------------------------- #
wp_nueva_sesion <- function(site, pausa = wp_pausa) {
  list(site = wp_normalizar_sitio(site), pausa = pausa, ultimo = 0)
}

wp_esperar <- function(sesion) {
  delta <- as.numeric(Sys.time()) - sesion$ultimo
  if (delta < sesion$pausa) Sys.sleep(sesion$pausa - delta)
  sesion$ultimo <- as.numeric(Sys.time())
  sesion
}

wp_espera_reintentar <- function(respuesta, intento) {
  # Segundos antes de reintentar una lectura transitoria. Respeta Retry-After
  # numerico; mayor que el tope devuelve NULL: el error se informa.
  crudo <- resp_header(respuesta, "retry-after") %||% resp_header(respuesta, "Retry-After")
  espera <- suppressWarnings(as.numeric(crudo))
  base <- c(1, 2)[min(intento, 2L)]
  if (!is.null(espera) && !is.na(espera)) espera <- max(espera, base) else espera <- base
  if (espera > wp_reintento_tope_s) NULL else espera
}

wp_get_interno <- function(sesion, url, params = list(), json = TRUE) {
  # GET de solo lectura con hasta wp_reintentos_max reintentos ante
  # 429/5xx/errores de red. Devuelve la respuesta tal cual, sin tratar
  # redirecciones: quien llama decide.
  sesion <- wp_esperar(sesion)
  intento <- 0L
  repeat {
    resultado <- tryCatch({
      req <- request(url) |>
        req_user_agent(wp_user_agent()) |>
        req_timeout(wp_timeout) |>
        req_options(followlocation = 0L) |>
        req_error(is_error = function(resp) FALSE)
      if (length(params)) req <- req |> req_url_query(!!!params)
      list(respuesta = req_perform(req))
    }, error = function(e) e)
    if (inherits(resultado, "error")) {
      if (intento >= wp_reintentos_max) stop(conditionMessage(resultado), call. = FALSE)
      Sys.sleep(c(1, 2)[min(intento + 1L, 2L)])
      sesion <- wp_esperar(sesion)
      intento <- intento + 1L
      next
    }
    respuesta <- resultado$respuesta
    estado <- resp_status(respuesta)
    if ((estado == 429L || estado >= 500L) && intento < wp_reintentos_max) {
      espera <- wp_espera_reintentar(respuesta, intento + 1L)
      if (is.null(espera)) break
      Sys.sleep(espera)
      sesion <- wp_esperar(sesion)
      intento <- intento + 1L
      next
    }
    break
  }
  respuesta <- resultado$respuesta
  texto <- tryCatch(resp_body_string(respuesta), error = function(e) "")
  cuerpo <- if (json) tryCatch(jsonlite::fromJSON(texto, simplifyVector = FALSE), error = function(e) NULL) else NULL
  list(respuesta = respuesta, sesion = sesion, texto = texto, cuerpo = cuerpo)
}

wp_get <- function(sesion, url, params = list(), json = TRUE) {
  # GET de colecciones: las redirecciones 3xx son error (redescubrir), igual
  # que el cliente Python.
  res <- wp_get_interno(sesion, url, params = params, json = json)
  if (resp_status(res$respuesta) %in% wp_redirecciones_http) {
    stop("Redireccion de API: redescubrir antes de consultar", call. = FALSE)
  }
  res
}

wp_probar_indice <- function(sesion, indice_url, fuente, restantes = 5L) {
  intento <- tryCatch(wp_get_interno(sesion, indice_url), error = function(e) e)
  if (inherits(intento, "error")) {
    return(list(ok = FALSE, error = "red", detalle = conditionMessage(intento),
                site = sesion$site, indice_url = indice_url, fuente = fuente))
  }
  respuesta <- intento$respuesta
  status <- resp_status(respuesta)
  tipo <- tolower(resp_header(respuesta, "content-type") %||% "")
  if (status %in% c(401L, 403L)) {
    return(list(ok = FALSE, error = paste0("http_", status), status = status,
                content_type = tipo, site = sesion$site, indice_url = indice_url,
                fuente = fuente, detalle = intento$texto))
  }
  if (status %in% wp_redirecciones_http) {
    destino <- NULL
    location <- resp_header(respuesta, "location") %||% resp_header(respuesta, "Location")
    if (!is.null(location) && nzchar(location)) {
      destino <- tryCatch(httr2::url_modify_relative(indice_url, location), error = function(e) NULL)
    }
    if (!is.null(destino) && !identical(destino, indice_url) && restantes > 0L &&
        identical(wp_origen_sitio(destino), wp_origen_sitio(indice_url))) {
      retorno <- wp_probar_indice(sesion, destino, fuente, restantes - 1L)
      if (isTRUE(retorno$ok) || retorno$error %in% c("http_401", "http_403")) return(retorno)
    }
    return(list(ok = FALSE, error = "red", status = status, content_type = tipo,
                site = sesion$site, indice_url = indice_url, fuente = fuente, detalle = intento$texto))
  }
  if (status >= 500L || status == 429L) {
    return(list(ok = FALSE, error = "red", status = status, content_type = tipo,
                site = sesion$site, indice_url = indice_url, fuente = fuente,
                detalle = intento$texto))
  }
  if (status == 200L && wp_indice_api_valido(intento$cuerpo)) {
    cuerpo <- intento$cuerpo
    rutas <- names(cuerpo$routes %||% list())
    return(list(
      ok = TRUE,
      site = sesion$site,
      indice_url = indice_url,
      api_base = wp_base_indice_api(indice_url),
      fuente = fuente,
      status = status,
      content_type = tipo,
      nombre = cuerpo$name %||% "",
      descripcion = cuerpo$description %||% "",
      namespaces = unlist(cuerpo$namespaces %||% character(0)),
      authentication = cuerpo$authentication %||% list(),
      rutas = rutas,
      rutas_clave = list(
        media = if ("/wp/v2/media" %in% rutas) "/wp/v2/media" else NULL,
        posts = if ("/wp/v2/posts" %in% rutas) "/wp/v2/posts" else NULL,
        pages = if ("/wp/v2/pages" %in% rutas) "/wp/v2/pages" else NULL
      )
    ))
  }
  if (status == 200L) {
    return(list(ok = FALSE, error = "indice_invalido", status = status,
                content_type = tipo, site = sesion$site, indice_url = indice_url,
                fuente = fuente, detalle = if (is.null(intento$cuerpo)) "respuesta no JSON" else "faltan namespaces/routes"))
  }
  list(ok = FALSE, error = "ausencia_api", status = status, content_type = tipo,
       site = sesion$site, indice_url = indice_url, fuente = fuente, detalle = intento$texto)
}

wp_descubrir_api <- function(sesion) {
  base <- wp_normalizar_sitio(sesion$site)
  candidatos <- list(
    list(fuente = "wp-json", indice_url = paste0(base, "/wp-json/")),
    list(fuente = "rest_route", indice_url = paste0(base, "/?rest_route=/"))
  )
  raiz <- tryCatch(wp_get_interno(sesion, base, json = FALSE), error = function(e) NULL)
  base_final <- if (!is.null(raiz)) raiz$respuesta$url %||% base else base
  link_api <- if (!is.null(raiz)) {
    tryCatch(wp_extraer_link_api(resp_header(raiz$respuesta, "link"), base_final), error = function(e) e)
  } else NULL
  if (inherits(link_api, "error")) {
    return(list(ok = FALSE, error = "link_invalido", site = sesion$site, indice_url = base,
                fuente = "link", detalle = conditionMessage(link_api), intentos = list()))
  }
  if (!is.null(link_api)) {
    candidatos[[length(candidatos) + 1L]] <- list(fuente = "link", indice_url = link_api)
  }

  intentos <- list()
  primero_red <- NULL
  primero_invalido <- NULL
  primero_ausencia <- NULL

  for (cand in candidatos) {
    info <- wp_probar_indice(sesion, cand$indice_url, cand$fuente)
    intentos[[length(intentos) + 1L]] <- info
    if (isTRUE(info$ok)) {
      info$intentos <- intentos
      return(info)
    }
    if (identical(info$error, "http_401") || identical(info$error, "http_403")) {
      info$intentos <- intentos
      return(info)
    }
    if (identical(info$error, "red")) {
      if (is.null(primero_red)) primero_red <- info
    } else if (identical(info$error, "indice_invalido")) {
      if (is.null(primero_invalido)) primero_invalido <- info
    } else if (is.null(primero_ausencia)) {
      primero_ausencia <- info
    }
  }

  fallo <- primero_red %||% primero_invalido %||% primero_ausencia
  if (is.null(fallo)) {
    fallo <- list(ok = FALSE, error = "ausencia_api", site = sesion$site,
                  detalle = "sin candidatos de descubrimiento")
  }
  fallo$ok <- FALSE
  fallo$intentos <- intentos
  fallo
}

wp_discover <- function(sesion) {
  info <- wp_descubrir_api(sesion)
  if (!isTRUE(info$ok)) info$mensaje <- wp_describir_error_descubrimiento(info)
  info
}

wp_resolver_api <- function(sesion) {
  info <- wp_descubrir_api(sesion)
  if (!isTRUE(info$ok)) stop(wp_describir_error_descubrimiento(info), call. = FALSE)
  sesion$api_base <- info$api_base
  sesion$api_indice <- info$indice_url
  sesion$api_fuente <- info$fuente
  sesion$api_nombre <- info$nombre %||% ""
  sesion$api_namespaces <- info$namespaces %||% character(0)
  sesion$api_rutas <- info$rutas %||% character(0)
  sesion$api_authentication <- info$authentication %||% list()
  sesion
}

wp_robots <- function(sesion) {
  res <- wp_get_interno(sesion, paste0(wp_origen_sitio(sesion$site), "/robots.txt"), json = FALSE)
  estado <- resp_status(res$respuesta)
  if (estado != 200) return(list(status = estado, texto = "", permite_uploads = NULL))
  texto <- res$texto
  list(status = estado, texto = texto,
       permite_uploads = wp_permite_robots(texto, "/wp-content/uploads/"),
       permite_rest = wp_permite_robots(texto, "/wp-json/"))
}

# -- lectura de colecciones -------------------------------------------------- #
wp_iterar_coleccion <- function(sesion, url, params = list(), max_items = NULL, per_page = wp_per_page_max) {
  # Itera una coleccion REST paginada; devuelve list(items, total, paginas).
  # Colecciones objeto (types/statuses/taxonomies) se envuelven con su clave
  # (__clave). Un objeto con 'code' (error WP) es error, no coleccion vacia.
  per_page <- max(1L, min(as.integer(per_page %||% wp_per_page_max), wp_per_page_max))
  if (!is.null(max_items) && !is.na(suppressWarnings(as.integer(max_items))) &&
      as.integer(max_items) > 0L) {
    per_page <- min(per_page, as.integer(max_items))
  }
  pagina <- 1L
  items <- list(); total <- NULL; paginas <- NULL
  repeat {
    consulta <- params
    consulta$per_page <- per_page
    consulta$page <- pagina
    res <- wp_get(sesion, url, consulta)
    status <- resp_status(res$respuesta)
    lote <- res$cuerpo
    if (status != 200L) {
      stop(sprintf("No se pudo leer %s (HTTP %s)", url, status), call. = FALSE)
    }
    if (is.list(lote) && length(names(lote)) > 0 && all(nzchar(names(lote)))) {
      if (!is.null(lote$code)) {
        stop(sprintf("La coleccion %s devolvio un error JSON: %s", url, lote$code), call. = FALSE)
      }
      if (pagina == 1L) {
        items <- lapply(names(lote), function(clave) {
          valor <- lote[[clave]]
          if (is.list(valor)) c(list(`__clave` = clave), valor) else list(`__clave` = clave, valor = valor)
        })
      }
      break
    }
    if (!is.list(lote)) stop(sprintf("La coleccion %s no devolvio una lista JSON", url), call. = FALSE)
    if (is.null(total)) {
      crudo <- resp_header(res$respuesta, "x-wp-total")
      total <- if (!is.null(crudo) && grepl("^[0-9]+$", crudo)) as.integer(crudo) else NULL
    }
    if (!length(lote)) break
    items <- c(items, lote)
    if (!is.null(max_items) && length(items) >= as.integer(max_items)) {
      items <- utils::head(items, as.integer(max_items))
      break
    }
    total_paginas <- as.integer(resp_header(res$respuesta, "x-wp-totalpages") %||% 1)
    paginas <- total_paginas
    if (pagina >= total_paginas) break
    pagina <- pagina + 1L
  }
  list(items = items, total = total, paginas = paginas %||% pagina)
}

wp_registro_desde_item <- function(sesion, item) {
  api_base <- sesion$api_base %||% wp_api_base(sesion$site)
  mime <- wp_normalizar_mime(item$mime_type %||% "")
  if (is.na(mime)) mime <- ""
  list(
    sitio = sesion$site,
    id = as.character(item$id %||% ""),
    titulo = (item$title %||% list())$rendered %||% "",
    slug = item$slug %||% "",
    fecha_media = item$date %||% "",
    mime_type = mime,
    familia = wp_familia_de_mime(mime),
    url_media = item$source_url %||% "",
    url_api = paste0(wp_ruta_media(api_base), "/", item$id %||% ""),
    bytes_api = (item$media_details %||% list())$filesize %||% NULL
  )
}

wp_listar_media <- function(sesion, mimes = NULL, search = NULL,
                            per_page = wp_per_page_max, max_items = NULL) {
  sesion <- wp_resolver_api(sesion)
  params <- list(orderby = "date", order = "desc",
                 `_fields` = "id,date,slug,title,source_url,mime_type,media_details")
  if (!is.null(mimes) && length(mimes)) params$mime_type <- paste(mimes, collapse = ",")
  if (!is.null(search) && nzchar(search)) params$search <- search
  res <- wp_iterar_coleccion(sesion, wp_ruta_media(sesion$api_base), params,
                             max_items = max_items, per_page = per_page)
  registros <- lapply(res$items, function(item) wp_registro_desde_item(sesion, item))
  list(registros = registros, sesion = sesion, total = res$total)
}

wp_obtener_media <- function(sesion, media_id) {
  sesion <- wp_resolver_api(sesion)
  url <- paste0(wp_ruta_media(sesion$api_base), "/", media_id)
  res <- wp_get(sesion, url)
  objeto <- res$cuerpo
  if (!is.list(objeto) || is.null(objeto$id)) {
    stop(sprintf("El ID %s no devolvio un objeto media", media_id), call. = FALSE)
  }
  list(registro = wp_registro_desde_item(sesion, objeto), sesion = sesion)
}

# -- descarga de medios ------------------------------------------------------ #
wp_descargar_archivo <- function(sesion, url, destino, intento = 0L) {
  # Descarga a <destino>.part siguiendo solo redirecciones del mismo origen.
  sesion <- wp_esperar(sesion)
  parcial <- paste0(destino, ".part")
  req <- request(url) |>
    req_user_agent(wp_user_agent()) |>
    req_timeout(wp_timeout) |>
    req_options(followlocation = 0L) |>
    req_error(is_error = function(resp) FALSE)
  resultado <- tryCatch(req_perform(req, path = parcial), error = function(e) e)
  if (inherits(resultado, "error")) {
    if (file.exists(parcial)) unlink(parcial)
    if (intento >= wp_reintentos_max) stop(conditionMessage(resultado), call. = FALSE)
    Sys.sleep(c(1, 2)[min(intento + 1L, 2L)])
    return(wp_descargar_archivo(sesion, url, destino, intento + 1L))
  }
  respuesta <- resultado
  estado <- resp_status(respuesta)
  if (estado %in% wp_redirecciones_http) {
    location <- resp_header(respuesta, "location") %||% resp_header(respuesta, "Location")
    destino_redir <- NULL
    if (!is.null(location) && nzchar(location)) {
      destino_redir <- tryCatch(httr2::url_modify_relative(url, location), error = function(e) NULL)
    }
    if (is.null(destino_redir) ||
        !identical(wp_origen_sitio(destino_redir), wp_origen_sitio(url))) {
      unlink(parcial)
      return(list(respuesta = respuesta, redir_ok = FALSE))
    }
    unlink(parcial)
    return(wp_descargar_archivo(sesion, destino_redir, destino, intento))
  }
  if (file.exists(parcial) && !file.exists(destino)) file.rename(parcial, destino)
  list(respuesta = respuesta, redir_ok = TRUE)
}

wp_descargar_media <- function(sesion, reg, outdir, sha_esperado = NULL) {
  invisible(wp_normalizar_sitio(reg$url_media))
  mime_esperado <- wp_normalizar_mime(reg$mime_type %||% "")
  if (is.na(mime_esperado)) {
    ext <- wp_extension_de_url(reg$url_media)
    mime_esperado <- if (!is.na(ext) && !is.null(wp_ext_a_mime[[ext]])) wp_ext_a_mime[[ext]] else NA_character_
  }
  destino_info <- wp_resolver_destino(mime_esperado, reg$url_media %||% "")
  carpeta <- file.path(outdir, destino_info$familia, wp_segmento_uploads(reg$url_media %||% ""))
  dir.create(carpeta, recursive = TRUE, showWarnings = FALSE)
  base <- wp_sanitizar_nombre(as.character(reg$id))
  slug <- wp_sanitizar_nombre(reg$slug %||% reg$titulo)
  nombre <- if (identical(slug, base)) paste0(base, ".", destino_info$ext)
  else sprintf("%s-%s.%s", base, slug, destino_info$ext)
  destino <- file.path(carpeta, nombre)
  paginas_de <- function(ruta) {
    if (identical(destino_info$ext, "pdf")) wp_contar_paginas(ruta) else ""
  }

  if (file.exists(destino) && !is.null(sha_esperado) && nzchar(sha_esperado)) {
    v <- wp_validar_archivo(destino, destino_info$firma, sha_esperado)
    if (isTRUE(v$valido)) {
      return(list(
        estado = "reutilizado", ruta = destino, sesion = sesion,
        fila = wp_fila_manifest(reg, archivo = destino, bytes = file.info(destino)$size,
                                sha256 = sha_esperado, paginas = paginas_de(destino),
                                estado = "reutilizado", motivo = "hash_coincide",
                                capturado_en_utc = wp_ahora_utc())
      ))
    }
  }

  descarga <- tryCatch(wp_descargar_archivo(sesion, reg$url_media, destino),
                       error = function(e) e)
  if (inherits(descarga, "error")) {
    return(list(estado = "error_http", ruta = NULL, sesion = sesion,
                fila = wp_fila_manifest(reg, estado = "error_http", motivo = "red_interrumpida",
                                        capturado_en_utc = wp_ahora_utc())))
  }
  respuesta <- descarga$respuesta
  estado <- resp_status(respuesta)
  tipo <- tolower(resp_header(respuesta, "content-type") %||% "")

  if (!isTRUE(descarga$redir_ok) || estado != 200L) {
    return(list(estado = "error_http", ruta = NULL, sesion = sesion,
                fila = wp_fila_manifest(reg, estado = "error_http",
                                        motivo = paste0("http_", estado),
                                        capturado_en_utc = wp_ahora_utc())))
  }
  if (!wp_tipo_contenido_aceptable(tipo, mime_esperado)) {
    if (file.exists(destino)) unlink(destino)
    return(list(estado = "tipo_inesperado", ruta = NULL, sesion = sesion,
                fila = wp_fila_manifest(reg, estado = "tipo_inesperado",
                                        motivo = paste0("content_type:",
                                                        if (nzchar(tipo)) tipo else "desconocido"),
                                        capturado_en_utc = wp_ahora_utc())))
  }

  if (!file.exists(destino)) {
    return(list(estado = "error_http", ruta = NULL, sesion = sesion,
                fila = wp_fila_manifest(reg, estado = "error_http", motivo = "descarga_vacia",
                                        capturado_en_utc = wp_ahora_utc())))
  }

  v <- wp_validar_archivo(destino, destino_info$firma)
  if (!isTRUE(v$valido)) {
    unlink(destino)
    return(list(estado = "invalido", ruta = NULL, sesion = sesion,
                fila = wp_fila_manifest(reg, estado = "invalido", motivo = v$motivo,
                                        capturado_en_utc = wp_ahora_utc())))
  }

  list(estado = "descargado", ruta = destino, sesion = sesion,
       fila = wp_fila_manifest(reg, archivo = destino, bytes = file.info(destino)$size,
                               sha256 = wp_sha256(destino), paginas = paginas_de(destino),
                               estado = "descargado", motivo = "ok",
                               capturado_en_utc = wp_ahora_utc()))
}

wp_tamano_remoto <- function(sesion, url) {
  invisible(wp_normalizar_sitio(url))
  tryCatch({
    sesion <- wp_esperar(sesion)
    req <- request(url) |> req_user_agent(wp_user_agent()) |> req_timeout(wp_timeout) |>
      req_method("HEAD") |> req_options(followlocation = 0L) |>
      req_error(is_error = function(resp) FALSE)
    largo <- resp_header(req_perform(req), "content-length")
    if (is.null(largo) || !grepl("^[0-9]+$", largo)) return(NA_integer_)
    as.integer(largo)
  }, error = function(e) NA_integer_)
}

wp_registro_desde_url <- function(sesion, url_media, id = NULL) {
  ext <- wp_extension_de_url(url_media)
  mime <- if (!is.na(ext) && !is.null(wp_ext_a_mime[[ext]])) wp_ext_a_mime[[ext]] else ""
  tamano <- wp_tamano_remoto(sesion, url_media)
  base <- wp_sanitizar_nombre(tools::file_path_sans_ext(basename(url_media)))
  list(sitio = sesion$site, id = id %||% base, titulo = base, slug = base,
       fecha_media = wp_segmento_uploads(url_media), mime_type = mime,
       url_media = url_media, url_api = "",
       bytes_api = if (is.na(tamano)) NULL else tamano)
}

# --------------------------------------------------------------------------- #
# Manifest en disco
# --------------------------------------------------------------------------- #
wp_leer_manifest <- function(ruta) {
  if (!file.exists(ruta)) return(wp_empty_manifest())
  df <- utils::read.csv(ruta, stringsAsFactors = FALSE, colClasses = "character",
                        fileEncoding = "UTF-8", check.names = FALSE)
  for (col in setdiff(wp_manifest_cols, names(df))) df[[col]] <- ""
  df[, wp_manifest_cols, drop = FALSE]
}

wp_escribir_manifest <- function(df, ruta) {
  dir.create(dirname(ruta), recursive = TRUE, showWarnings = FALSE)
  utils::write.csv(df[, wp_manifest_cols, drop = FALSE], ruta, row.names = FALSE,
                   fileEncoding = "UTF-8")
}

# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
wp_resumen_estados <- function(df) {
  if (!nrow(df)) return(stats::setNames(list(), character(0)))
  t <- table(df$estado)
  as.list(stats::setNames(as.integer(t), names(t)))
}

wp_cmd_discover <- function(args) {
  sesion <- wp_nueva_sesion(args$site)
  info <- wp_discover(sesion)
  cat(jsonlite::toJSON(list(discover = info, robots = wp_robots(sesion)),
                       auto_unbox = TRUE, pretty = TRUE, null = "null"), "\n")
  if (isTRUE(info$ok)) 0L else 1L
}

wp_cmd_robots <- function(args) {
  cat(jsonlite::toJSON(wp_robots(wp_nueva_sesion(args$site)),
                       auto_unbox = TRUE, pretty = TRUE, null = "null"), "\n")
  0L
}

wp_cmd_media <- function(args) {
  mimes <- wp_resolver_mimes(args$mime)
  sesion <- wp_nueva_sesion(args$site, pausa = as.numeric(args$sleep %||% wp_pausa))
  res <- wp_listar_media(sesion, mimes = mimes, search = args$search,
                         per_page = args$`per-page` %||% wp_per_page_max,
                         max_items = args$max)
  cat(jsonlite::toJSON(list(
    total_disponible = res$total,
    filtros = list(mime = args$mime %||% NULL, search = args$search %||% NULL),
    total_listado = length(res$registros), registros = res$registros
  ), auto_unbox = TRUE, pretty = TRUE, null = "null"), "\n")
  0L
}

wp_cmd_preflight <- function(args) {
  mimes <- wp_resolver_mimes(args$mime)
  sesion <- wp_nueva_sesion(args$site, pausa = as.numeric(args$sleep %||% wp_pausa))
  res <- wp_listar_media(sesion, mimes = mimes, search = args$search,
                         per_page = args$`per-page` %||% wp_per_page_max,
                         max_items = args$max %||% (wp_umbral_confirmacion + 1L))
  umbral <- as.integer(args$umbral %||% wp_umbral_confirmacion)
  resumen <- wp_resumen_preflight(res$sesion, res$registros, total = res$total,
                                  consulta = trimws(sprintf("mime=%s search=%s",
                                                            args$mime %||% "todos",
                                                            args$search %||% "")))
  resumen$umbral_confirmacion <- umbral
  resumen$requiere_confirmacion <- wp_requiere_confirmacion(length(res$registros), umbral)
  cat(jsonlite::toJSON(resumen, auto_unbox = TRUE, pretty = TRUE, null = "null"), "\n")
  0L
}

wp_cmd_download <- function(args) {
  mimes <- wp_resolver_mimes(args$mime)
  sesion <- wp_nueva_sesion(args$site, pausa = as.numeric(args$sleep %||% wp_pausa))
  outdir <- args$out %||% "datos"
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  manifest_path <- file.path(outdir, "manifest.csv")
  previas <- wp_leer_manifest(manifest_path)
  total <- NULL

  if (!is.null(args$url) && nzchar(args$url)) {
    registros <- list(wp_registro_desde_url(sesion, args$url, args$id))
  } else if (!is.null(args$id) && nzchar(args$id)) {
    res_id <- wp_obtener_media(sesion, args$id)
    registros <- list(res_id$registro); sesion <- res_id$sesion
  } else {
    res <- wp_listar_media(sesion, mimes = mimes, search = args$search,
                           per_page = args$`per-page` %||% wp_per_page_max,
                           max_items = args$max %||% 3)
    registros <- res$registros; sesion <- res$sesion; total <- res$total
  }

  umbral <- as.integer(args$umbral %||% wp_umbral_confirmacion)
  consulta <- trimws(sprintf("mime=%s search=%s", args$mime %||% "todos", args$search %||% ""))
  resumen <- wp_resumen_preflight(sesion, registros, total = total,
                                  consulta = if (nzchar(consulta)) consulta else (args$url %||% ""))
  resumen$umbral_confirmacion <- umbral
  message(jsonlite::toJSON(list(preflight = resumen), auto_unbox = TRUE))

  if (wp_requiere_confirmacion(length(registros), umbral, args$`confirmo-bajar`)) {
    message(jsonlite::toJSON(list(
      error = "requiere_confirmacion",
      a_descargar = length(registros),
      umbral = umbral,
      instruccion = sprintf("Nada se descargo. Revisar el preflight y repetir con --confirmo-bajar %d para bajar ese lote exacto.",
                            length(registros))
    ), auto_unbox = TRUE))
    return(3L)
  }

  filas <- wp_empty_manifest()
  for (reg in registros) {
    sha_previo <- previas$sha256[match(reg$id, previas$id)]
    res <- wp_descargar_media(sesion, reg, outdir,
                              sha_esperado = if (length(sha_previo) && !is.na(sha_previo)) sha_previo else NULL)
    sesion <- res$sesion
    message(sprintf("[%s] id=%s %s", res$estado, reg$id, substr(reg$titulo, 1, 60)))
    filas <- rbind(filas, res$fila)
  }

  combinado <- wp_upsert_manifest(previas, filas)
  wp_escribir_manifest(combinado, manifest_path)
  cat(jsonlite::toJSON(list(manifest = manifest_path, nuevas = nrow(filas),
                            resumen = wp_resumen_estados(combinado)),
                       auto_unbox = TRUE, pretty = TRUE), "\n")
  if (any(wp_estados_fallo %in% combinado$estado)) 1L else 0L
}

wp_resolver_recurso <- function(recurso) {
  texto <- trimws(recurso %||% "")
  texto <- gsub("^/+|/+$", "", texto)
  if (!nzchar(texto)) {
    stop("Falta --recurso (posts, pages, media, categories, tags, users, comments, ...)", call. = FALSE)
  }
  if (!is.null(wp_recursos_export[[texto]])) return(wp_recursos_export[[texto]])
  if (!grepl("^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$", texto) ||
      any(strsplit(texto, "/", fixed = TRUE)[[1]] == "..")) {
    stop(sprintf("Recurso invalido: '%s'. Usar un atajo o una ruta relativa como 'wp/v2/posts'", recurso), call. = FALSE)
  }
  texto
}

wp_nombre_export <- function(ruta, filtros, campos) {
  # (id de manifiesto, nombre de archivo) estables. El ID del objeto ya queda
  # en la ruta; solo filtros y campos generan la huella distintiva. La huella
  # usa una cadena canonica compartida con el CLI Python: el mismo filtro
  # produce el mismo archivo y la misma fila de manifiesto en ambos lenguajes.
  base <- gsub("/", "-", gsub("^/+|/+$", "", ruta))
  carga <- paste0("campos=", campos %||% "")
  if (length(filtros)) {
    pares <- vapply(sort(names(filtros)), function(k) paste0(k, "=", filtros[[k]]), character(1))
    carga <- paste(carga, paste(pares, collapse = "&"), sep = "|")
  }
  huella <- ""
  if (length(filtros) || (!is.null(campos) && nzchar(campos))) {
    huella <- substr(digest::digest(carga, algo = "sha256", serialize = FALSE), 1, 8)
  }
  ident <- paste0("export:", gsub("^/+|/+$", "", ruta))
  if (nzchar(huella)) ident <- paste0(ident, "#", huella)
  nombre <- paste0(base, if (nzchar(huella)) paste0("-", huella) else "")
  list(ident = ident, base = nombre)
}

wp_cmd_export <- function(args) {
  sesion <- wp_nueva_sesion(args$site, pausa = as.numeric(args$sleep %||% wp_pausa))
  outdir <- args$out %||% "datos"
  carpeta <- file.path(outdir, "json")
  dir.create(carpeta, recursive = TRUE, showWarnings = FALSE)
  manifest_path <- file.path(outdir, "manifest.csv")
  previas <- wp_leer_manifest(manifest_path)
  formato <- args$formato %||% "json"

  ruta <- wp_resolver_recurso(args$recurso)
  tiene_id <- !is.null(args$id) && nzchar(args$id)
  if (tiene_id) ruta <- paste0(ruta, "/", args$id)

  filtros <- list()
  for (par in args$filtro %||% character(0)) {
    trozo <- strsplit(par, "=", fixed = TRUE)[[1]]
    if (length(trozo) < 2L || !nzchar(trozo[1]) || !nzchar(trozo[2])) {
      stop(sprintf("--filtro espera clave=valor, recibido: '%s'", par), call. = FALSE)
    }
    filtros[[trozo[1]]] <- trozo[2]
  }
  if (!is.null(args$search) && nzchar(args$search)) filtros$search <- args$search
  params <- filtros
  if (!is.null(args$campos) && nzchar(args$campos)) params$`_fields` <- args$campos

  sesion <- wp_resolver_api(sesion)
  url <- wp_ruta_coleccion(sesion$api_base, ruta)

  # Freno antes de consultar: solicitudes estimadas, no items.
  per_page_efectiva <- max(1L, min(as.integer(args$`per-page` %||% wp_per_page_max), wp_per_page_max))
  max_items <- as.integer(args$max %||% 100L)
  solicitudes <- if (tiene_id) 1L else max(1L, ceiling(max(1L, max_items) / per_page_efectiva))
  umbral <- as.integer(args$umbral %||% wp_umbral_confirmacion)
  message(jsonlite::toJSON(list(preflight = list(
    sitio = sesion$site, recurso = ruta,
    max_items = if (tiene_id) NULL else max_items,
    solicitudes_estimadas = solicitudes, umbral_confirmacion = umbral
  )), auto_unbox = TRUE))
  if (wp_requiere_confirmacion(solicitudes, umbral, args$`confirmo-bajar`)) {
    message(jsonlite::toJSON(list(
      error = "requiere_confirmacion",
      solicitudes_estimadas = solicitudes,
      umbral = umbral,
      instruccion = sprintf("Nada se exporto. Revisar el preflight y repetir con --confirmo-bajar %d para ese alcance exacto.",
                            solicitudes)
    ), auto_unbox = TRUE))
    return(3L)
  }

  if (tiene_id) {
    res <- wp_get(sesion, url, params)
    if (!is.list(res$cuerpo)) stop(sprintf("%s no devolvio un objeto JSON", url), call. = FALSE)
    items <- list(res$cuerpo); total <- NULL; paginas <- NULL
  } else {
    res <- wp_iterar_coleccion(sesion, url, params, max_items = max_items,
                               per_page = args$`per-page` %||% wp_per_page_max)
    items <- res$items; total <- res$total; paginas <- res$paginas
  }

  nombres <- wp_nombre_export(ruta, filtros, args$campos)
  destino <- file.path(carpeta, paste0(nombres$base, ".", formato))
  if (identical(formato, "ndjson")) {
    lineas <- vapply(items, function(item) jsonlite::toJSON(item, auto_unbox = TRUE), character(1))
    writeLines(lineas, destino, useBytes = TRUE)
  } else {
    envoltura <- list(
      sitio = sesion$site, recurso = ruta, ruta_api = url, filtros = filtros,
      campos = if (is.null(args$campos) || !nzchar(args$campos)) NULL else args$campos,
      total_disponible = total, paginas_recorridas = paginas, items = items,
      capturado_en_utc = wp_ahora_utc()
    )
    writeLines(jsonlite::toJSON(envoltura, auto_unbox = TRUE, pretty = TRUE, null = "null"),
               destino, useBytes = TRUE)
  }

  registro <- list(sitio = sesion$site, id = nombres$ident,
                   titulo = paste("Export", ruta), slug = basename(destino),
                   fecha_media = "", mime_type = "application/json", url_media = "",
                   url_api = url, bytes_api = file.info(destino)$size)
  fila <- wp_fila_manifest(registro, archivo = destino, bytes = file.info(destino)$size,
                           sha256 = wp_sha256(destino), paginas = "",
                           estado = "exportado", motivo = sprintf("items:%d", length(items)),
                           capturado_en_utc = wp_ahora_utc())
  combinado <- wp_upsert_manifest(previas, fila)
  wp_escribir_manifest(combinado, manifest_path)
  cat(jsonlite::toJSON(list(archivo = destino, items = length(items),
                            total_disponible = total, manifest = manifest_path),
                       auto_unbox = TRUE, pretty = TRUE, null = "null"), "\n")
  0L
}

wp_verificar_fila <- function(fila) {
  ruta <- fila$archivo
  ext <- tolower(tools::file_ext(ruta))
  if (ext %in% c("json", "ndjson") || identical(wp_normalizar_mime(fila$mime_type), "application/json")) {
    if (!nzchar(ruta) || !file.exists(ruta)) return(list(valido = FALSE, motivo = "archivo_ausente"))
    if (identical(ext, "ndjson")) {
      lineas <- readLines(ruta, warn = FALSE, encoding = "UTF-8")
      lineas <- lineas[nzchar(trimws(lineas))]
      if (!length(lineas)) return(list(valido = FALSE, motivo = "archivo_vacio"))
      ok <- all(vapply(lineas, function(l) {
        !inherits(tryCatch(jsonlite::fromJSON(l, simplifyVector = FALSE), error = function(e) e), "error")
      }, logical(1)))
      if (!ok) return(list(valido = FALSE, motivo = "json_invalido"))
    } else {
      v <- wp_verificar_firma(ruta, "json")
      if (!isTRUE(v$valido)) return(v)
    }
  } else {
    mime <- wp_normalizar_mime(fila$mime_type)
    firma <- wp_firma_de_mime(mime)
    if (is.na(firma) && !is.null(wp_ext_a_mime[[ext]])) firma <- wp_firma_de_mime(wp_ext_a_mime[[ext]])
    if (identical(ext, "pdf") && is.na(mime)) firma <- "pdf"
    v <- wp_verificar_firma(ruta, firma)
    if (!isTRUE(v$valido)) return(v)
  }
  if (nzchar(fila$sha256)) {
    if (!identical(tolower(wp_sha256(ruta)), tolower(fila$sha256))) {
      return(list(valido = FALSE, motivo = "hash_mismatch"))
    }
  }
  list(valido = TRUE, motivo = "ok")
}

wp_cmd_verify <- function(args) {
  outdir <- args$out %||% "datos"
  manifest_path <- file.path(outdir, "manifest.csv")
  df <- wp_leer_manifest(manifest_path)
  if (!nrow(df)) {
    cat(jsonlite::toJSON(list(manifest = manifest_path, filas = 0, error = "manifest_ausente"),
                         auto_unbox = TRUE), "\n")
    return(1L)
  }
  detalle <- vector("list", nrow(df))
  for (i in seq_len(nrow(df))) {
    fila <- df[i, ]
    if (fila$estado %in% wp_estados_ok && nzchar(fila$archivo) && file.exists(fila$archivo)) {
      v <- wp_verificar_fila(fila)
    } else {
      v <- list(valido = FALSE, motivo = "sin_archivo")
    }
    detalle[[i]] <- list(id = fila$id, estado = fila$estado, valido = v$valido, motivo = v$motivo)
  }
  validas <- sum(vapply(detalle, function(d) isTRUE(d$valido), logical(1)))
  cat(jsonlite::toJSON(list(manifest = manifest_path, filas = nrow(df), validas = validas,
                            detalle = detalle), auto_unbox = TRUE, pretty = TRUE), "\n")
  if (validas == nrow(df)) 0L else 1L
}

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
wp_parse_args <- function(argv) {
  comandos <- c("discover", "robots", "media", "preflight", "download", "export", "verify")
  if (!length(argv)) {
    stop(sprintf("Falta el comando (%s)", paste(comandos, collapse = "|")), call. = FALSE)
  }
  args <- list(comando = argv[1])
  i <- 2L
  while (i <= length(argv)) {
    token <- argv[i]
    if (startsWith(token, "--")) {
      clave <- sub("^--", "", token)
      if (i < length(argv) && !startsWith(argv[i + 1], "--")) {
        if (identical(clave, "filtro")) {
          args$filtro <- c(args$filtro, argv[i + 1])
        } else {
          args[[clave]] <- argv[i + 1]
        }
        i <- i + 2L
      } else {
        args[[clave]] <- TRUE
        i <- i + 1L
      }
    } else i <- i + 1L
  }
  if (args$comando %in% c("discover", "robots", "media", "download", "preflight", "export") &&
      is.null(args$site)) {
    stop(sprintf("El comando '%s' requiere --site", args$comando), call. = FALSE)
  }
  if (identical(args$comando, "export") && is.null(args$recurso)) {
    stop("El comando 'export' requiere --recurso", call. = FALSE)
  }
  args
}

wp_main <- function(argv = commandArgs(trailingOnly = TRUE)) {
  args <- wp_parse_args(argv)
  switch(args$comando,
    discover = wp_cmd_discover(args),
    robots = wp_cmd_robots(args),
    media = wp_cmd_media(args),
    preflight = wp_cmd_preflight(args),
    download = wp_cmd_download(args),
    export = wp_cmd_export(args),
    verify = wp_cmd_verify(args),
    stop(sprintf("Comando desconocido: %s", args$comando), call. = FALSE)
  )
}

if (sys.nframe() == 0L && !interactive()) {
  codigo <- tryCatch(wp_main(), error = function(e) { message("ERROR: ", conditionMessage(e)); 2L })
  quit(status = codigo)
}
