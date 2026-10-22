# Pruebas de wp_api.R sin red: utilidades puras, firmas de formato, descarga
# con sesion falsa, exportacion y verificacion de manifiesto.

suppressPackageStartupMessages({
  library(httr2)
  library(jsonlite)
  library(digest)
})

arg_file <- grep("^--file=", commandArgs(FALSE), value = TRUE)
aqui <- if (length(arg_file)) dirname(normalizePath(sub("^--file=", "", arg_file[1]))) else getwd()
if (!file.exists(file.path(aqui, "wp_api.R"))) {
  aqui <- file.path(getwd(), "wp-api", "assets")
}
source(file.path(aqui, "wp_api.R"), local = TRUE)

fallos <- character()
check <- function(expr, etiqueta) {
  ok <- FALSE; msg <- NULL
  tryCatch({ ok <- isTRUE(expr) }, error = function(e) { ok <<- FALSE; msg <<- conditionMessage(e) })
  if (!ok) fallos <<- c(fallos, if (is.null(msg)) etiqueta else paste0(etiqueta, ": ", msg))
}

fake_resp <- function(status = 200L, headers = list()) {
  structure(list(status_code = as.integer(status), headers = headers), class = "fake_resp")
}

td <- tempfile(); dir.create(td)
escribir <- function(nombre, datos) {
  ruta <- file.path(td, nombre)
  writeBin(if (is.raw(datos)) datos else charToRaw(datos), ruta)
  ruta
}

# --- Sitios y URLs ---------------------------------------------------------- #
check(identical(wp_normalizar_sitio("ejemplo.com"), "https://ejemplo.com"), "normaliza_sin_esquema")
check(identical(wp_normalizar_sitio("https://ejemplo.com/"), "https://ejemplo.com"), "normaliza_barra_final")
check(identical(wp_normalizar_sitio("http://ejemplo.com/blog/a/b?x=1"), "http://ejemplo.com/blog/a/b"), "normaliza_preserva_subdir")
check(inherits(tryCatch(wp_normalizar_sitio(""), error = identity), "error"), "rechaza_sitio_vacio")
check(inherits(tryCatch(wp_normalizar_sitio("https://user:pass@ejemplo.com/blog"), error = identity), "error"), "rechaza_userinfo")
check(identical(wp_ruta_media("https://ejemplo.com/blog/?rest_route="), "https://ejemplo.com/blog/?rest_route=/wp/v2/media"), "ruta_media_rest_route")
check(identical(wp_ruta_coleccion("https://ejemplo.com/wp-json", "wp/v2/posts"),
                "https://ejemplo.com/wp-json/wp/v2/posts"), "ruta_coleccion_wp_json")
check(identical(wp_ruta_coleccion("https://ejemplo.com/blog/?rest_route=/", "wc/v3/products"),
                "https://ejemplo.com/blog/?rest_route=%2Fwc%2Fv3%2Fproducts"), "ruta_coleccion_rest_route")
check(inherits(tryCatch(wp_ruta_coleccion("https://ejemplo.com/wp-json", "../wp/v2/admin"), error = identity), "error"), "ruta_coleccion_rechaza_dos_puntos")

# --- Registro de formatos --------------------------------------------------- #
check(identical(wp_familia_de_mime("application/pdf"), "documentos"), "familia_pdf")
check(identical(wp_familia_de_mime("application/vnd.openxmlformats-officedocument.wordprocessingml.document"), "documentos"), "familia_docx")
check(identical(wp_familia_de_mime("image/svg+xml"), "imagenes"), "familia_svg")
check(identical(wp_familia_de_mime("audio/mpeg"), "audio"), "familia_mp3")
check(identical(wp_familia_de_mime("video/mp4"), "video"), "familia_mp4")
check(identical(wp_familia_de_mime("application/zip"), "comprimidos"), "familia_zip")
check(identical(wp_familia_de_mime("text/csv"), "datos"), "familia_csv")
check(identical(wp_familia_de_mime("image/x-fancy"), "imagenes"), "familia_prefijo_imagen")

check(identical(wp_resolver_mimes("pdf"), "application/pdf"), "mimes_alias_simple")
check(identical(wp_resolver_mimes("pdf,jpg"), c("application/pdf", "image/jpeg")), "mimes_lista")
check(is.null(wp_resolver_mimes(NULL)), "mimes_sin_filtro")
check(is.null(wp_resolver_mimes("todos")), "mimes_todos")
check(inherits(tryCatch(wp_resolver_mimes("docx2"), error = identity), "error"), "mimes_desconocido_error")

dest <- wp_resolver_destino("application/pdf", "https://x/a.pdf")
check(identical(dest$ext, "pdf") && identical(dest$familia, "documentos") && identical(dest$firma, "pdf"), "destino_pdf")
dest <- wp_resolver_destino("image/jpeg", "https://x/a.jpeg")
check(identical(dest$ext, "jpeg") && identical(dest$familia, "imagenes"), "destino_alias_extension_url")
dest <- wp_resolver_destino(NULL, "https://x/a.mp3")
check(identical(dest$ext, "mp3") && identical(dest$familia, "audio"), "destino_desde_extension")
dest <- wp_resolver_destino(NULL, "https://x/archivo.zzz")
check(identical(dest$ext, "zzz") && identical(dest$familia, "otros") && is.na(dest$firma), "destino_desconocido")

check(isTRUE(wp_tipo_contenido_aceptable("application/pdf", "application/pdf")), "ct_exacto")
check(isTRUE(wp_tipo_contenido_aceptable("application/octet-stream", "application/pdf")), "ct_generico")
check(isTRUE(wp_tipo_contenido_aceptable("audio/x-wav", "audio/wav")), "ct_misma_familia")
check(isFALSE(wp_tipo_contenido_aceptable("text/html; charset=UTF-8", "application/pdf")), "ct_html_rechazado")
check(isFALSE(wp_tipo_contenido_aceptable("image/png", "application/pdf")), "ct_familia_distinta")

# --- Firmas de bytes -------------------------------------------------------- #
check(isTRUE(wp_verificar_firma(escribir("a.pdf", "%PDF-1.7\n%demo"), "pdf")$valido), "firma_pdf")
check(isTRUE(wp_verificar_firma(escribir("a.zip", as.raw(c(0x50, 0x4B, 0x03, 0x04, 0x14, 0x00))), "zip")$valido), "firma_zip")
check(isTRUE(wp_verificar_firma(escribir("a.png", as.raw(c(0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A))), "png")$valido), "firma_png")
check(isTRUE(wp_verificar_firma(escribir("a.jpg", as.raw(c(0xFF, 0xD8, 0xFF, 0xE0))), "jpg")$valido), "firma_jpg")
check(isTRUE(wp_verificar_firma(escribir("a.gif", as.raw(c(0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00, 0x01, 0x00))), "gif")$valido), "firma_gif")
check(isTRUE(wp_verificar_firma(escribir("a.doc", as.raw(c(0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1))), "ole")$valido), "firma_ole")
check(isTRUE(wp_verificar_firma(escribir("a.mp4", as.raw(c(0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70))), "ftyp")$valido), "firma_ftyp")
check(isTRUE(wp_verificar_firma(escribir("a.mp3", as.raw(c(0x49, 0x44, 0x33, 0x03, 0x00, 0x00, 0x00))), "mp3")$valido), "firma_mp3_id3")
tar_bytes <- as.raw(rep(0, 300))
tar_bytes[258:262] <- charToRaw("ustar")
check(isTRUE(wp_verificar_firma(escribir("a.tar", tar_bytes), "tar")$valido), "firma_tar")
check(identical(wp_verificar_firma(escribir("a.json", '{"a": [1, 2]}'), "json")$valido, TRUE), "firma_json_ok")
check(identical(wp_verificar_firma(escribir("b.json", '{"a": [1,'), "json")$motivo, "json_invalido"), "firma_json_roto")
check(identical(wp_verificar_firma(escribir("a.svg", '<?xml version="1.0"?><svg xmlns="x"/>'), "svg")$valido, TRUE), "firma_svg_ok")
check(identical(wp_verificar_firma(escribir("b.svg", "<html><body>403</body></html>"), "svg")$motivo, "parece_html"), "firma_svg_html")
check(identical(wp_verificar_firma(escribir("a.csv", "a,b\n1,2\n"), NA_character_)$valido, TRUE), "firma_csv_ok")
check(identical(wp_verificar_firma(escribir("b.csv", "<!DOCTYPE html><html>x"), NA_character_)$motivo, "parece_html"), "firma_csv_html")
check(identical(wp_verificar_firma(escribir("a.png", "%PDF-1.4"), "png")$motivo, "firma:no_es_png"), "firma_incorrecta_motivo")
vacio <- file.path(td, "vacio.bin"); invisible(file.create(vacio))
check(identical(wp_verificar_firma(vacio, "pdf")$motivo, "archivo_vacio"), "firma_vacio")
check(identical(wp_verificar_firma(file.path(td, "nada.bin"), "pdf")$motivo, "archivo_ausente"), "firma_ausente")
pdf_ok <- escribir("hash.pdf", "%PDF-1.4 contenido")
check(isTRUE(wp_validar_archivo(pdf_ok, "pdf", wp_sha256(pdf_ok))$valido), "validar_hash_ok")
check(identical(wp_validar_archivo(pdf_ok, "pdf", strrep("0", 64))$motivo, "hash_mismatch"), "validar_hash_alterado")

# --- robots, nombres, manifest ---------------------------------------------- #
yoast <- "# START YOAST BLOCK\nUser-agent: *\nDisallow:\n\nSitemap: https://x/sitemap.xml\n"
check(isTRUE(wp_permite_robots(yoast, "/wp-content/uploads/x.pdf")), "robots_yoast_permite")
bloqueado <- "User-agent: *\nDisallow: /wp-content/uploads/\n"
check(isFALSE(wp_permite_robots(bloqueado, "/wp-content/uploads/x.pdf")), "robots_bloquea_uploads")
check(isTRUE(wp_permite_robots(bloqueado, "/otra/ruta")), "robots_permite_otra_ruta")
check(isTRUE(wp_permite_robots("", "/cualquiera")), "robots_vacio_permite")
check(identical(wp_sanitizar_nombre("Silos granja"), "Silos-granja"), "sanitiza_espacios")
check(!grepl("[/\\\\]", wp_sanitizar_nombre("../../etc/passwd")), "sanitiza_rutas")
check(nchar(wp_sanitizar_nombre(strrep("a", 200))) <= 80, "sanitiza_longitud")
check(identical(wp_segmento_uploads("https://x/wp-content/uploads/2024/10/a.pdf"), "2024/10"), "segmento_uploads")

fila <- function(sitio, id, estado) wp_fila_manifest(list(sitio = sitio, id = id, titulo = paste0("t", id)), estado = estado)
previas <- rbind(wp_empty_manifest(), fila("https://a", "1", "descargado"))
nuevas <- rbind(wp_empty_manifest(),
                fila("https://a", "1", "reutilizado"),
                fila("https://a", "2", "descargado"),
                fila("https://b", "1", "descargado"))
combinado <- wp_upsert_manifest(previas, nuevas)
check(nrow(combinado) == 3, "dedup_por_sitio_id")
check(identical(combinado$estado[combinado$sitio == "https://a" & combinado$id == "1"], "reutilizado"), "actualiza_estado_existente")
check(identical(nrow(wp_upsert_manifest(combinado, nuevas)), 3L), "reejecutar_no_duplica")
mf <- file.path(td, "manifest.csv")
wp_escribir_manifest(combinado, mf)
leido <- wp_leer_manifest(mf)
check(nrow(leido) == 3 && identical(names(leido), wp_manifest_cols), "manifest_round_trip")

# --- Descarga multi-formato con sesion falsa -------------------------------- #
con_descarga_falsa <- function(bytes, content_type, extra_headers = list()) {
  original_descarga <- wp_descargar_archivo
  original_status <- resp_status
  original_header <- resp_header
  assign("wp_descargar_archivo", function(sesion, url, destino, intento = 0L) {
    writeBin(bytes, paste0(destino, ".part"))
    file.rename(paste0(destino, ".part"), destino)
    list(respuesta = fake_resp(200L, c(list(`content-type` = content_type), extra_headers)), redir_ok = TRUE)
  }, envir = globalenv())
  assign("resp_status", function(resp) resp$status_code, envir = globalenv())
  assign("resp_header", function(resp, name) resp$headers[[name]], envir = globalenv())
  function() {
    assign("wp_descargar_archivo", original_descarga, envir = globalenv())
    assign("resp_status", original_status, envir = globalenv())
    assign("resp_header", original_header, envir = globalenv())
  }
}

pdf_bin <- charToRaw("%PDF-1.4\n1 0 obj\n<<>>\nendobj\n")
png_bin <- as.raw(c(0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D))
sesion0 <- list(site = "https://ejemplo.com", pausa = 0, ultimo = 0)

restaurar <- con_descarga_falsa(pdf_bin, "application/pdf")
res <- wp_descargar_media(sesion0, list(sitio = "https://ejemplo.com", id = "9", titulo = "T", slug = "t",
                                        mime_type = "application/pdf",
                                        url_media = "https://ejemplo.com/wp-content/uploads/2024/10/a.pdf"), td)
restaurar()
check(identical(res$estado, "descargado"), "descarga_pdf_estado")
check(identical(normalizePath(res$ruta), normalizePath(file.path(td, "documentos", "2024", "10", "9-t.pdf"))), "descarga_pdf_ruta")
check(identical(res$fila$sha256, wp_sha256(res$ruta)), "descarga_pdf_sha")

restaurar <- con_descarga_falsa(png_bin, "image/png")
res <- wp_descargar_media(sesion0, list(sitio = "https://ejemplo.com", id = "21", titulo = "L", slug = "logo",
                                        mime_type = "image/png",
                                        url_media = "https://ejemplo.com/wp-content/uploads/2025/01/logo.png"), td)
restaurar()
check(identical(res$estado, "descargado"), "descarga_png_estado")
check(grepl("imagenes", res$ruta, fixed = TRUE), "descarga_png_familia")

restaurar <- con_descarga_falsa(charToRaw("<html>403</html>"), "text/html; charset=UTF-8")
res <- wp_descargar_media(sesion0, list(sitio = "https://ejemplo.com", id = "9", titulo = "T", slug = "t",
                                        mime_type = "application/pdf", url_media = "https://ejemplo.com/x.pdf"), td)
restaurar()
check(identical(res$estado, "tipo_inesperado"), "descarga_html_tipo_inesperado")
check(grepl("text/html", res$fila$motivo, fixed = TRUE), "descarga_html_motivo")

restaurar <- con_descarga_falsa(charToRaw("<html>error</html>"), "application/pdf")
res <- wp_descargar_media(sesion0, list(sitio = "https://ejemplo.com", id = "9", titulo = "T", slug = "t",
                                        mime_type = "application/pdf", url_media = "https://ejemplo.com/x.pdf"), td)
restaurar()
check(identical(res$estado, "invalido"), "descarga_html_disfrazado_invalido")
check(identical(res$fila$motivo, "firma:no_es_pdf"), "descarga_html_disfrazado_motivo")
check(!file.exists(file.path(td, "documentos", "sin-fecha", "9-t.pdf")), "descarga_invalida_no_conserva_archivo")

# Reutilizacion por hash: sin red
ruta_pdf <- file.path(td, "documentos", "2024", "10", "9-t.pdf")
restaurar <- con_descarga_falsa(pdf_bin, "application/pdf")
primer_sha <- wp_sha256(ruta_pdf)
res <- wp_descargar_media(sesion0, list(sitio = "https://ejemplo.com", id = "9", titulo = "T", slug = "t",
                                        mime_type = "application/pdf",
                                        url_media = "https://ejemplo.com/wp-content/uploads/2024/10/a.pdf"),
                          td, sha_esperado = primer_sha)
restaurar()
check(identical(res$estado, "reutilizado"), "reutiliza_hash_coincidente")

# Freno de volumen a nivel comando
original_descarga <- wp_descargar_archivo
assign("wp_descargar_archivo", function(...) stop("Peticion inesperada durante el freno", call. = FALSE), envir = globalenv())
original_resolver <- wp_resolver_api
assign("wp_resolver_api", function(sesion) { sesion$api_base <- "https://ejemplo.com/wp-json"; sesion }, envir = globalenv())
original_get <- wp_get
assign("wp_get", function(sesion, url, params = list(), json = TRUE) {
  list(respuesta = fake_resp(200L, list(`content-type` = "application/json", `x-wp-total` = "2", `x-wp-totalpages` = "1")),
       sesion = sesion, texto = "", cuerpo = list(
         list(id = 1, title = list(rendered = "a"), slug = "a", source_url = "https://e/a.pdf", mime_type = "application/pdf"),
         list(id = 2, title = list(rendered = "b"), slug = "b", source_url = "https://e/b.pdf", mime_type = "application/pdf")
       ))
}, envir = globalenv())
original_status <- resp_status; original_header <- resp_header
assign("resp_status", function(resp) resp$status_code, envir = globalenv())
assign("resp_header", function(resp, name) resp$headers[[name]], envir = globalenv())
tryCatch({
  td_dl <- file.path(td, "dl"); dir.create(td_dl, recursive = TRUE)
  args_dl <- list(site = "https://ejemplo.com", search = "x", url = NULL, id = NULL, mime = NULL,
                  `per-page` = "100", max = "2", sleep = "0", out = td_dl, umbral = "1",
                  `confirmo-bajar` = NULL)
  codigo <- suppressMessages(wp_cmd_download(args_dl))
  check(identical(codigo, 3L), "frena_download_sin_confirmacion")
  args_dl$`confirmo-bajar` <- "2"
  assign("wp_descargar_archivo", function(sesion, url, destino, intento = 0L) {
    writeBin(pdf_bin, paste0(destino, ".part")); file.rename(paste0(destino, ".part"), destino)
    list(respuesta = fake_resp(200L, list(`content-type` = "application/pdf")), redir_ok = TRUE)
  }, envir = globalenv())
  codigo <- suppressMessages(wp_cmd_download(args_dl))
  check(identical(codigo, 0L), "confirma_y_descarga")
  filas_dl <- wp_leer_manifest(file.path(td_dl, "manifest.csv"))
  check(nrow(filas_dl) == 2 && all(filas_dl$estado == "descargado"), "manifest_dos_descargas")
}, finally = {
  assign("wp_descargar_archivo", original_descarga, envir = globalenv())
  assign("wp_resolver_api", original_resolver, envir = globalenv())
  assign("wp_get", original_get, envir = globalenv())
  assign("resp_status", original_status, envir = globalenv())
  assign("resp_header", original_header, envir = globalenv())
})

# --- Exportacion ------------------------------------------------------------ #
check(identical(wp_resolver_recurso("posts"), "wp/v2/posts"), "recurso_atajo")
check(identical(wp_resolver_recurso("wc/v3/products"), "wc/v3/products"), "recurso_ruta")
check(inherits(tryCatch(wp_resolver_recurso("../etc"), error = identity), "error"), "recurso_invalido")
nombres <- wp_nombre_export("wp/v2/posts", list(), NULL)
check(identical(nombres$ident, "export:wp/v2/posts"), "nombre_export_base")
nombres_f <- wp_nombre_export("wp/v2/posts", list(after = "2024-01-01"), "id,title")
check(grepl("#", nombres_f$ident, fixed = TRUE) && grepl("-", nombres_f$base, fixed = TRUE), "nombre_export_con_huella")
check(!identical(nombres$base, nombres_f$base), "nombre_export_distinto_por_filtros")

original_resolver <- wp_resolver_api
original_get <- wp_get
original_status <- resp_status; original_header <- resp_header
assign("wp_resolver_api", function(sesion) { sesion$api_base <- "https://ejemplo.com/wp-json"; sesion }, envir = globalenv())
assign("wp_get", function(sesion, url, params = list(), json = TRUE) {
  attr(url, "params") <- params
  .ultima_url <<- url
  .ultimos_params <<- params
  list(respuesta = fake_resp(200L, list(`content-type` = "application/json", `x-wp-total` = "2", `x-wp-totalpages` = "1")),
       sesion = sesion, texto = "",
       cuerpo = list(list(id = 101, title = list(rendered = "Uno")), list(id = 102, title = list(rendered = "Dos"))))
}, envir = globalenv())
assign("resp_status", function(resp) resp$status_code, envir = globalenv())
assign("resp_header", function(resp, name) resp$headers[[name]], envir = globalenv())
tryCatch({
  td_exp <- file.path(td, "exp"); dir.create(td_exp, recursive = TRUE)
  args_exp <- function(...) {
    base <- list(site = "https://ejemplo.com", recurso = "posts", id = NULL, search = NULL,
                 filtro = NULL, campos = NULL, formato = "json", `per-page` = "100",
                 max = "5", sleep = "0", out = td_exp, umbral = "5", `confirmo-bajar` = NULL)
    utils::modifyList(base, list(...))
  }
  salida <- suppressMessages(capture.output(codigo <- wp_cmd_export(args_exp())))
  check(identical(codigo, 0L), "export_json_codigo")
  destino <- file.path(td_exp, "json", "wp-v2-posts.json")
  check(file.exists(destino), "export_json_archivo")
  envoltura <- jsonlite::fromJSON(destino, simplifyVector = FALSE)
  check(identical(envoltura$recurso, "wp/v2/posts"), "export_json_recurso")
  check(identical(vapply(envoltura$items, function(i) i$id, numeric(1)), c(101, 102)), "export_json_items")
  filas_exp <- wp_leer_manifest(file.path(td_exp, "manifest.csv"))
  check(identical(filas_exp$estado[1], "exportado"), "export_json_estado")

  salida <- suppressMessages(capture.output(codigo <- wp_cmd_export(args_exp(formato = "ndjson", filtro = c("after=2024-01-01"), campos = "id,title"))))
  check(identical(codigo, 0L), "export_ndjson_codigo")
  ndjson <- list.files(file.path(td_exp, "json"), pattern = "\\.ndjson$")
  check(length(ndjson) == 1, "export_ndjson_archivo")
  lineas <- readLines(file.path(td_exp, "json", ndjson[1]), encoding = "UTF-8")
  check(identical(as.numeric(jsonlite::fromJSON(lineas[1])$id), 101), "export_ndjson_lineas")
  check(identical(.ultimos_params$after, "2024-01-01"), "export_filtros_en_query")
  check(identical(.ultimos_params$`_fields`, "id,title"), "export_campos_en_query")

  # Freno por solicitudes estimadas: max=1000, per-page=100 -> 10 > umbral 5
  codigo <- suppressMessages(wp_cmd_export(args_exp(max = "1000", umbral = "5")))
  check(identical(codigo, 3L), "export_frena_solicitudes")
  codigo <- suppressMessages(wp_cmd_export(args_exp(max = "1000", umbral = "5", `confirmo-bajar` = "10")))
  check(identical(codigo, 0L), "export_confirma_solicitudes")

  # Coleccion objeto (types): items envueltos con su clave
  assign("wp_get", function(sesion, url, params = list(), json = TRUE) {
    list(respuesta = fake_resp(200L, list(`content-type` = "application/json")),
         sesion = sesion, texto = "",
         cuerpo = list(post = list(name = "Posts", rest_base = "posts"), page = list(name = "Pages")))
  }, envir = globalenv())
  salida <- suppressMessages(capture.output(codigo <- wp_cmd_export(args_exp(recurso = "types", max = "1"))))
  check(identical(codigo, 0L), "export_types_codigo")
  env_tipos <- jsonlite::fromJSON(file.path(td_exp, "json", "wp-v2-types.json"), simplifyVector = FALSE)
  claves <- vapply(env_tipos$items, function(i) i$`__clave`, character(1))
  check(setequal(claves, c("post", "page")), "export_types_envuelve_clave")

  # --id: objeto unico, sin huella en el nombre
  assign("wp_get", function(sesion, url, params = list(), json = TRUE) {
    check(grepl("/wp/v2/posts/17$", url), "export_id_url")
    list(respuesta = fake_resp(200L, list(`content-type` = "application/json")),
         sesion = sesion, texto = "", cuerpo = list(id = 17, slug = "entrada"))
  }, envir = globalenv())
  salida <- suppressMessages(capture.output(codigo <- wp_cmd_export(args_exp(id = "17"))))
  check(identical(codigo, 0L), "export_id_codigo")
  check(file.exists(file.path(td_exp, "json", "wp-v2-posts-17.json")), "export_id_archivo")

  # Error WP (dict con code) no es coleccion vacia
  assign("wp_get", function(sesion, url, params = list(), json = TRUE) {
    list(respuesta = fake_resp(200L, list(`content-type` = "application/json")),
         sesion = sesion, texto = "", cuerpo = list(code = "rest_no_route", message = "x"))
  }, envir = globalenv())
  res_error <- tryCatch(suppressMessages(wp_cmd_export(args_exp(recurso = "statuses"))), error = identity)
  check(inherits(res_error, "error"), "export_error_wp_no_vacio")
}, finally = {
  assign("wp_resolver_api", original_resolver, envir = globalenv())
  assign("wp_get", original_get, envir = globalenv())
  assign("resp_status", original_status, envir = globalenv())
  assign("resp_header", original_header, envir = globalenv())
})

# --- Verificacion de manifiesto mixto --------------------------------------- #
td_ver <- file.path(td, "ver"); dir.create(file.path(td_ver, "documentos"), recursive = TRUE)
dir.create(file.path(td_ver, "json"), recursive = TRUE)
dir.create(file.path(td_ver, "imagenes"), recursive = TRUE)
writeBin(pdf_bin, file.path(td_ver, "documentos", "a.pdf"))
writeBin(png_bin, file.path(td_ver, "imagenes", "b.png"))
writeBin(charToRaw('{"items": []}'), file.path(td_ver, "json", "wp-v2-posts.json"))
writeBin(charToRaw('{"id":1}\n{"id":2}\n'), file.path(td_ver, "json", "tags.ndjson"))
writeBin(pdf_bin, file.path(td_ver, "documentos", "viejo.pdf"))
fila_ver <- function(id, archivo, mime, estado) {
  wp_fila_manifest(list(sitio = "https://ejemplo.com", id = id, mime_type = mime, url_media = ""),
                   archivo = archivo, sha256 = wp_sha256(archivo), estado = estado)
}
mixto <- rbind(wp_empty_manifest(),
               fila_ver("1", file.path(td_ver, "documentos", "a.pdf"), "application/pdf", "descargado"),
               fila_ver("2", file.path(td_ver, "imagenes", "b.png"), "image/png", "descargado"),
               fila_ver("3", file.path(td_ver, "json", "wp-v2-posts.json"), "application/json", "exportado"),
               fila_ver("4", file.path(td_ver, "json", "tags.ndjson"), "application/json", "exportado"),
               fila_ver("5", file.path(td_ver, "documentos", "viejo.pdf"), "application/pdf", "descargado_pdf"))
wp_escribir_manifest(mixto, file.path(td_ver, "manifest.csv"))
check(identical(wp_cmd_verify(list(out = td_ver)), 0L), "verify_mixto_ok")

roto <- mixto
roto$archivo[3] <- file.path(td_ver, "json", "roto.json")
writeBin(charToRaw('{"a": '), file.path(td_ver, "json", "roto.json"))
wp_escribir_manifest(roto, file.path(td_ver, "manifest.csv"))
check(identical(wp_cmd_verify(list(out = td_ver)), 1L), "verify_json_roto_falla")

alterado <- mixto
alterado$sha256[1] <- strrep("0", 64)
wp_escribir_manifest(alterado, file.path(td_ver, "manifest.csv"))
check(identical(wp_cmd_verify(list(out = td_ver)), 1L), "verify_hash_alterado_falla")

# --- Descubrimiento con sesion falsa ---------------------------------------- #
original_interno <- wp_get_interno
original_status <- resp_status; original_header <- resp_header
assign("wp_get_interno", function(sesion, url, params = list(), json = TRUE) {
  if (identical(url, "https://ejemplo.com/blog") || identical(url, "https://ejemplo.com/blog/")) {
    return(list(respuesta = fake_resp(200L, list(`content-type` = "text/html")), sesion = sesion,
                texto = "<html></html>", cuerpo = NULL))
  }
  if (grepl("/wp-json/?$", url)) {
    return(list(respuesta = fake_resp(403L, list(`content-type` = "text/html")), sesion = sesion,
                texto = "<html>403</html>", cuerpo = NULL))
  }
  if (grepl("\\?rest_route=/$", url)) {
    return(list(respuesta = fake_resp(200L, list(`content-type` = "application/json")), sesion = sesion,
                texto = "",
                cuerpo = list(name = "Sitio", description = "Desc", namespaces = c("wp/v2"),
                              routes = list(`/wp/v2/media` = list(), `/wp/v2/posts` = list()))))
  }
  stop(sprintf("url inesperada: %s", url), call. = FALSE)
}, envir = globalenv())
assign("resp_status", function(resp) resp$status_code, envir = globalenv())
assign("resp_header", function(resp, name) resp$headers[[name]], envir = globalenv())
tryCatch({
  info <- wp_descubrir_api(list(site = "https://ejemplo.com/blog", ultimo = 0, pausa = 0))
  check(!isTRUE(info$ok) && identical(info$error, "http_403"), "descubre_detiene_bloqueo")
}, finally = {
  assign("wp_get_interno", original_interno, envir = globalenv())
  assign("resp_status", original_status, envir = globalenv())
  assign("resp_header", original_header, envir = globalenv())
})

# 3xx en colecciones: error, no seguir a ciegas
assign("wp_get_interno", function(sesion, url, params = list(), json = TRUE) {
  list(respuesta = fake_resp(302L, list(location = "https://otro.origen/wp-json/wp/v2/posts")),
       sesion = sesion, texto = "", cuerpo = NULL)
}, envir = globalenv())
tryCatch({
  res_redir <- tryCatch(wp_get(list(site = "https://ejemplo.com", pausa = 0, ultimo = 0),
                               "https://ejemplo.com/wp-json/wp/v2/posts"), error = identity)
  check(inherits(res_redir, "error"), "coleccion_redireccion_es_error")
}, finally = {
  assign("wp_get_interno", original_interno, envir = globalenv())
})

# --- CLI -------------------------------------------------------------------- #
check(inherits(tryCatch(wp_parse_args(c("download")), error = identity), "error"), "cli_exige_site")
args <- wp_parse_args(c("download", "--site", "https://x", "--search", "catalogo", "--max", "1", "--mime", "pdf,jpg"))
check(identical(args$mime, "pdf,jpg"), "cli_parsea_mime")
args_f <- wp_parse_args(c("export", "--site", "https://x", "--recurso", "posts",
                          "--filtro", "after=2024-01-01", "--filtro", "per_page=x"))
check(identical(length(args_f$filtro), 2L), "cli_filtro_repetible")
check(inherits(tryCatch(wp_parse_args(c("export", "--site", "https://x")), error = identity), "error"), "cli_export_exige_recurso")
check(inherits(tryCatch(wp_parse_args(c("media")), error = identity), "error"), "cli_media_exige_site")

# Freno de volumen: semantica del numero exacto
check(isFALSE(wp_requiere_confirmacion(5, 5)), "freno_en_el_umbral_no_frena")
check(isTRUE(wp_requiere_confirmacion(6, 5)), "freno_sobre_umbral")
check(isFALSE(wp_requiere_confirmacion(6, 5, 6)), "freno_confirma_numero_exacto")
check(isTRUE(wp_requiere_confirmacion(6, 5, 7)), "freno_rechaza_numero_equivocado")

# Paginas PDF reales via pdftools
if (requireNamespace("pdftools", quietly = TRUE)) {
  multipagina <- file.path(td, "dos-paginas.pdf")
  grDevices::pdf(multipagina)
  graphics::plot(1, 1); graphics::plot(2, 2)
  invisible(grDevices::dev.off())
  check(identical(wp_contar_paginas(multipagina), 2L), "cuenta_paginas_reales")
}

unlink(td, recursive = TRUE)
if (length(fallos)) stop(paste(fallos, collapse = "\n"), call. = FALSE)
cat("ok\n")
