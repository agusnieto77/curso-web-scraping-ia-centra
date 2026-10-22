#!/usr/bin/env python3
"""Cliente minimo para la API REST de WordPress: descarga verificada de medios
de cualquier formato y exportacion JSON de colecciones REST.

Uso:
    python wp_api.py discover --site https://ejemplo.com
    python wp_api.py robots   --site https://ejemplo.com
    python wp_api.py media    --site https://ejemplo.com --mime pdf --search "catalogo" --max 5
    python wp_api.py download --site https://ejemplo.com --mime pdf,jpg --max 1 --out datos
    python wp_api.py download --site https://ejemplo.com --url https://.../archivo.ext --out datos
    python wp_api.py download --site https://ejemplo.com --id 123 --out datos
    python wp_api.py export   --site https://ejemplo.com --recurso posts --max 100 --out datos
    python wp_api.py verify   --out datos

Solo usa endpoints publicos de lectura (GET). No envia credenciales.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests

try:  # Windows no trae CA del sistema para OpenSSL: usar el almacen del SO.
    import truststore

    truststore.inject_into_ssl()
    TLS_FUENTE = "system"
except Exception:  # pragma: no cover - entornos sin truststore
    TLS_FUENTE = "certifi"

USER_AGENT = (
    "curso-web-scraping-ia-centra/1.0 (docencia; contacto: agusnieto77) "
    "requests/{v}".format(v=requests.__version__)
)
TIMEOUT = 30.0
PAUSA = 1.0  # segundos entre solicitudes: no martillar el servidor.
PER_PAGE_MAX = 100  # tope duro de la API REST de WordPress.
UMBRAL_CONFIRMACION = 5  # por encima de esto, exigir --confirmo-bajar N
REINTENTOS_MAX = 2  # solo lecturas transitorias (429/5xx/red), nunca escrituras
REINTENTO_TOPE_S = 20.0  # Retry-After mayor: no esperar, devolver el error
REDIRECCIONES_HTTP = {301, 302, 303, 307, 308}

# Estados de exito del manifiesto. Los *_pdf son de manifiestos historicos y
# siguen verificandose para no romper evidencia previa.
ESTADOS_OK = {"descargado", "reutilizado", "exportado", "descargado_pdf", "reutilizado_pdf"}
ESTADOS_FALLO = {"error_http", "tipo_inesperado", "invalido", "error_url"}


class WpDiscoveryError(RuntimeError):
    def __init__(self, info: dict):
        self.info = info
        super().__init__(describir_error_descubrimiento(info))


# --------------------------------------------------------------------------- #
# Registro de formatos: MIME -> (extensiones, familia, firma de bytes)
# Cubre los tipos que WordPress acepta en la biblioteca de medios
# (wp_get_mime_types + get_allowed_mime_types) y textos/enlaces habituales.
# --------------------------------------------------------------------------- #
REGISTRO_MIME: dict[str, tuple[tuple[str, ...], str, str | None]] = {
    # Documentos
    "application/pdf": (("pdf",), "documentos", "pdf"),
    "application/x-pdf": (("pdf",), "documentos", "pdf"),
    "application/msword": (("doc",), "documentos", "ole"),
    "application/vnd.msword": (("doc",), "documentos", "ole"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (("docx",), "documentos", "zip"),
    "application/vnd.ms-excel": (("xls",), "documentos", "ole"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (("xlsx",), "documentos", "zip"),
    "application/vnd.ms-powerpoint": (("ppt",), "documentos", "ole"),
    "application/vnd.ms-powerpoint.presentation.macroEnabled.7": (("ppt",), "documentos", "ole"),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (("pptx",), "documentos", "zip"),
    "application/vnd.oasis.opendocument.text": (("odt",), "documentos", "zip"),
    "application/vnd.oasis.opendocument.spreadsheet": (("ods",), "documentos", "zip"),
    "application/vnd.oasis.opendocument.presentation": (("odp",), "documentos", "zip"),
    "application/rtf": (("rtf",), "documentos", "rtf"),
    "text/plain": (("txt", "asc", "c", "cc", "h", "srt", "md"), "documentos", "texto"),
    "text/calendar": (("ics",), "documentos", "ics"),
    # Datos
    "application/json": (("json",), "datos", "json"),
    "text/csv": (("csv",), "datos", "texto"),
    "text/tab-separated-values": (("tsv",), "datos", "texto"),
    "application/xml": (("xml",), "datos", "xml"),
    "text/xml": (("xml",), "datos", "xml"),
    # Imagenes
    "image/jpeg": (("jpg", "jpeg", "jpe"), "imagenes", "jpg"),
    "image/pjpeg": (("jpg",), "imagenes", "jpg"),
    "image/png": (("png",), "imagenes", "png"),
    "image/gif": (("gif",), "imagenes", "gif"),
    "image/webp": (("webp",), "imagenes", "webp"),
    "image/avif": (("avif",), "imagenes", "ftyp"),
    "image/heic": (("heic",), "imagenes", "ftyp"),
    "image/bmp": (("bmp",), "imagenes", "bmp"),
    "image/tiff": (("tiff", "tif"), "imagenes", "tiff"),
    "image/x-icon": (("ico",), "imagenes", "ico"),
    "image/svg+xml": (("svg",), "imagenes", "svg"),
    "image/vnd.adobe.photoshop": (("psd",), "imagenes", "psd"),
    # Audio
    "audio/mpeg": (("mp3", "m4a", "m4b"), "audio", "mp3"),
    "audio/mp4": (("m4a",), "audio", "ftyp"),
    "audio/x-m4a": (("m4a",), "audio", "ftyp"),
    "audio/ogg": (("ogg", "oga"), "audio", "ogg"),
    "audio/wav": (("wav",), "audio", "wav"),
    "audio/x-wav": (("wav",), "audio", "wav"),
    "audio/wave": (("wav",), "audio", "wav"),
    "audio/flac": (("flac",), "audio", "flac"),
    "audio/aac": (("aac",), "audio", "aac"),
    "audio/x-matroska": (("mka",), "audio", "ebml"),
    "audio/midi": (("mid", "midi"), "audio", "mid"),
    "audio/x-realaudio": (("ra", "ram"), "audio", None),
    "audio/x-ms-wma": (("wma",), "audio", "asf"),
    # Video
    "video/mp4": (("mp4", "m4v"), "video", "ftyp"),
    "video/x-m4v": (("m4v",), "video", "ftyp"),
    "video/quicktime": (("mov", "qt"), "video", "ftyp"),
    "video/x-msvideo": (("avi",), "video", "avi"),
    "video/x-ms-wmv": (("wmv",), "video", "asf"),
    "video/x-matroska": (("mkv",), "video", "ebml"),
    "video/webm": (("webm",), "video", "ebml"),
    "video/x-flv": (("flv",), "video", "flv"),
    "video/mpeg": (("mpeg", "mpg", "mpe"), "video", "mpeg"),
    "video/3gpp": (("3gp",), "video", "ftyp"),
    "video/3gpp2": (("3g2",), "video", "ftyp"),
    # Comprimidos
    "application/zip": (("zip",), "comprimidos", "zip"),
    "application/x-zip-compressed": (("zip",), "comprimidos", "zip"),
    "application/x-gzip": (("gz", "gzip"), "comprimidos", "gzip"),
    "application/gzip": (("gz",), "comprimidos", "gzip"),
    "application/x-tar": (("tar",), "comprimidos", "tar"),
    "application/x-rar-compressed": (("rar",), "comprimidos", "rar"),
    "application/x-7z-compressed": (("7z",), "comprimidos", "7z"),
    # Otros
    "application/x-shockwave-flash": (("swf",), "otros", "swf"),
    "application/x-msdownload": (("exe",), "otros", "exe"),
    "application/octet-stream": (("bin",), "otros", None),
}

ALIAS_MIME = {
    "x-pdf": "pdf",
    "pjpeg": "jpg",
    "jpeg": "jpg",
    "jpe": "jpg",
    "tif": "tiff",
    "oga": "ogg",
    "m4v": "mp4",
    "qt": "mov",
    "mpg": "mpeg",
    "mpe": "mpeg",
    "gzip": "gz",
}

EXT_A_MIME: dict[str, str] = {}
for _mime, (_exts, _fam, _fir) in REGISTRO_MIME.items():
    for _ext in _exts:
        EXT_A_MIME.setdefault(_ext, _mime)

FAMILIAS = ["documentos", "datos", "imagenes", "audio", "video", "comprimidos", "otros"]

RECURSOS_EXPORT = {
    "posts": "wp/v2/posts",
    "pages": "wp/v2/pages",
    "media": "wp/v2/media",
    "categories": "wp/v2/categories",
    "tags": "wp/v2/tags",
    "users": "wp/v2/users",
    "comments": "wp/v2/comments",
    "types": "wp/v2/types",
    "statuses": "wp/v2/statuses",
    "taxonomies": "wp/v2/taxonomies",
    "search": "wp/v2/search",
    "settings": "wp/v2/settings",
}


# --------------------------------------------------------------------------- #
# Utilidades de URL
# --------------------------------------------------------------------------- #
def _normalizar_url(url: str, conservar_query: bool = False) -> str:
    if not url:
        raise ValueError("URL de sitio vacia")
    texto = url.strip()
    partes = urlparse(texto)
    if not partes.scheme:
        texto = "https://" + texto
        partes = urlparse(texto)
    if partes.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"URL de sitio invalida: {url!r}")
    if not partes.netloc:
        raise ValueError(f"URL de sitio invalida: {url!r}")
    if partes.username or partes.password or "@" in partes.netloc:
        raise ValueError("URL de sitio no debe incluir userinfo")
    ruta = partes.path if conservar_query and partes.query else partes.path.rstrip("/")
    query = partes.query if conservar_query else ""
    return urlunparse((partes.scheme, partes.netloc, ruta, "", query, ""))


def _es_indice_rest(url: str) -> bool:
    partes = urlparse(url)
    ruta = partes.path.rstrip("/")
    return "rest_route=" in (partes.query or "").lower() or ruta.endswith("/wp-json")


def _base_indice_api(indice_url: str) -> str:
    return indice_url.rstrip("/")


def _mismo_origen(origen: str, destino: str) -> bool:
    a = urlparse(origen)
    b = urlparse(destino)
    if b.scheme not in {"http", "https"} or not b.netloc or b.username or b.password or "@" in b.netloc:
        return False
    try:
        return (
            a.scheme.lower() == b.scheme.lower()
            and (a.hostname or "").lower() == (b.hostname or "").lower()
            and (a.port or (443 if a.scheme == "https" else 80))
            == (b.port or (443 if b.scheme == "https" else 80))
        )
    except ValueError:
        return False


def _redirigir_seguro(origen: str, resp) -> str | None:
    location = resp.headers.get("location") or resp.headers.get("Location")
    if not location:
        return None
    destino = urljoin(origen, location)
    if not _mismo_origen(origen, destino):
        return None
    return destino


def _ancestros_url(url: str) -> list[str]:
    partes = urlparse(normalizar_sitio(url))
    segmentos = [seg for seg in partes.path.split("/") if seg]
    candidatos = []
    for i in range(len(segmentos), max(-1, len(segmentos) - 3), -1):
        ruta = "/" + "/".join(segmentos[:i]) if i else ""
        candidato = urlunparse((partes.scheme, partes.netloc, ruta, "", "", ""))
        if candidato not in candidatos:
            candidatos.append(candidato)
    return candidatos


def _extraer_link_api(texto: str | None, base_url: str) -> str | None:
    if not texto:
        return None
    patrones = (
        r'<([^>]+)>;\s*rel=["\']https://api\.w\.org/["\']',
        r'rel=["\']https://api\.w\.org/["\'][^>]*href=["\']([^"\']+)["\']',
        r'href=["\']([^"\']+)["\'][^>]*rel=["\']https://api\.w\.org/["\']',
    )
    for patron in patrones:
        m = re.search(patron, texto, flags=re.I)
        if m:
            return urljoin(base_url, m.group(1))
    return None


def _indice_api_valido(cuerpo) -> bool:
    return (
        isinstance(cuerpo, dict)
        and isinstance(cuerpo.get("routes"), dict)
        and bool(cuerpo["routes"])
        and isinstance(cuerpo.get("namespaces"), list)
        and all(isinstance(ns, str) for ns in cuerpo["namespaces"])
    )


def _validar_url_publica(url: str, etiqueta: str = "URL") -> str:
    texto = _normalizar_url(url, conservar_query=True)
    partes = urlparse(texto)
    if partes.scheme not in {"http", "https"}:
        raise ValueError(f"{etiqueta} debe usar http o https")
    if not partes.netloc:
        raise ValueError(f"{etiqueta} invalida")
    if partes.username or partes.password or "@" in partes.netloc:
        raise ValueError(f"{etiqueta} no debe incluir userinfo")
    return texto


def describir_error_descubrimiento(info: dict) -> str:
    error = info.get("error")
    sitio = info.get("site") or info.get("url_inicio") or "<sitio>"
    indice = info.get("indice_url") or sitio
    if error in {"http_401", "http_403"}:
        return f"API REST restringida ({error}) en {indice}"
    if error == "red":
        detalle = info.get("detalle")
        return f"Error de red al descubrir API REST en {sitio}" + (f" ({detalle})" if detalle else "")
    if error == "indice_invalido":
        return (f"Indice REST invalido en {indice}"
                f" (status {info.get('status')}, content-type {info.get('content_type') or 'desconocido'})")
    return f"No se encontro una API REST valida en {sitio} (probo /wp-json/, ?rest_route=/ y Link api.w.org)"


MANIFEST_COLUMNS = [
    "sitio",
    "id",
    "titulo",
    "slug",
    "fecha_media",
    "mime_type",
    "url_media",
    "url_api",
    "archivo",
    "bytes",
    "sha256",
    "paginas",
    "estado",
    "motivo",
    "licencia",
    "capturado_en_utc",
]


# --------------------------------------------------------------------------- #
# Registro de formatos: resolucion y validacion
# --------------------------------------------------------------------------- #
def normalizar_mime(mime: str | None) -> str | None:
    """Base del MIME, sin parametros y en minusculas; '' si falta."""
    if not mime:
        return None
    return (mime or "").split(";")[0].strip().lower() or None


def descripcion_mime(mime: str | None) -> tuple[tuple[str, ...], str, str | None] | None:
    entrada = REGISTRO_MIME.get(normalizar_mime(mime) or "")
    if entrada:
        return entrada
    alias = ALIAS_MIME.get((normalizar_mime(mime) or "").split("/")[-1])
    return REGISTRO_MIME.get(alias) if alias else None


def familia_de_mime(mime: str | None) -> str:
    entrada = descripcion_mime(mime)
    if entrada:
        return entrada[1]
    base = normalizar_mime(mime) or ""
    if base.startswith("image/"):
        return "imagenes"
    if base.startswith("audio/"):
        return "audio"
    if base.startswith("video/"):
        return "video"
    return "otros"


def firma_de_mime(mime: str | None) -> str | None:
    entrada = descripcion_mime(mime)
    return entrada[2] if entrada else None


def extension_de_mime(mime: str | None) -> str | None:
    entrada = descripcion_mime(mime)
    return entrada[0][0] if entrada else None


def extension_de_url(url: str) -> str | None:
    ext = Path(urlparse(url).path).suffix.lstrip(".").lower()
    return ext or None


def resolver_destino(mime: str | None, url_media: str) -> tuple[str, str, str | None]:
    """(extension, familia, firma) para guardar un archivo.

    Prioriza el MIME informado por la API; si falta, deduce desde la
    extension de la URL. Extension desconocida: 'bin' en familia otros.
    """
    ext_url = extension_de_url(url_media)
    entrada = descripcion_mime(mime)
    if entrada:
        exts, familia, firma = entrada
        if ext_url in exts:
            return ext_url, familia, firma
        return exts[0], familia, firma
    if ext_url and ext_url in EXT_A_MIME:
        return resolver_destino(EXT_A_MIME[ext_url], url_media)
    return (ext_url or "bin", familia_de_mime(mime), None)


def resolver_mimes(texto: str | None) -> list[str] | None:
    """Traduce 'pdf,jpg' o 'application/pdf,image/jpeg' a lista de MIMEs.

    None o 'todos' significa sin filtro. Los alias son las extensiones del
    registro. Un token desconocido es error: mejor fallar antes de filtrar
    de mas o de menos en el servidor.
    """
    if not texto:
        return None
    tokens = [t.strip().lower() for t in re.split(r"[,\s]+", texto) if t.strip()]
    if not tokens or any(t in {"*", "todos", "all"} for t in tokens):
        return None
    mimes: list[str] = []
    for token in tokens:
        if token in EXT_A_MIME:
            mimes.append(EXT_A_MIME[token])
        elif normalizar_mime(token) in REGISTRO_MIME:
            mimes.append(normalizar_mime(token))
        else:
            conocidos = ", ".join(sorted(EXT_A_MIME))
            raise ValueError(f"MIME o alias desconocido: {token!r}. Alias conocidos: {conocidos}")
    return list(dict.fromkeys(mimes))


def tipo_contenido_aceptable(content_type: str | None, mime_esperado: str | None) -> bool:
    """El Content-Type servido debe ser el esperado, generico o de la misma
    familia. text/html nunca es aceptable para un archivo descargable."""
    base = normalizar_mime(content_type)
    if not base:
        return True  # servidor sin content-type: valida la firma de bytes
    if base in {"text/html", "application/xhtml+xml"}:
        return False
    if not mime_esperado:
        return True
    if base == normalizar_mime(mime_esperado):
        return True
    if base in {"application/octet-stream", "application/binary", "binary/octet-stream"}:
        return True
    return familia_de_mime(base) == familia_de_mime(mime_esperado)


def verificar_firma(ruta: Path, firma: str | None):
    """(valido, motivo) segun los bytes magicos del archivo.

    'firma' es el tipo de firma del registro. None significa formato sin
    firma confiable (csv, ra, binario desconocido): solo se rechaza HTML
    disfrazado. Ninguna firma demuestra que el archivo sea seguro de abrir.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        return False, "archivo_ausente"
    if ruta.stat().st_size == 0:
        return False, "archivo_vacio"
    with open(ruta, "rb") as fh:
        cab = fh.read(64)
        if firma == "tar":
            fh.seek(257)
            extra = fh.read(8)
        else:
            extra = b""
    if cab.startswith(b"\xef\xbb\xbf"):  # BOM UTF-8
        cab = cab[3:]
    if firma == "pdf":
        ok = cab.startswith(b"%PDF-")
    elif firma == "zip":
        ok = cab[:4] in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}
    elif firma == "7z":
        ok = cab.startswith(b"7z\xbc\xaf\x27\x1c")
    elif firma == "rar":
        ok = cab.startswith(b"Rar!\x1a\x07")
    elif firma == "gzip":
        ok = cab.startswith(b"\x1f\x8b")
    elif firma == "tar":
        ok = extra.startswith(b"ustar")
    elif firma == "ole":  # DOC/XLS/PPT legados (compound file)
        ok = cab.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    elif firma == "png":
        ok = cab.startswith(b"\x89PNG\r\n\x1a\n")
    elif firma == "jpg":
        ok = cab.startswith(b"\xff\xd8\xff")
    elif firma == "gif":
        ok = cab[:6] in {b"GIF87a", b"GIF89a"}
    elif firma == "webp":
        ok = cab[:4] == b"RIFF" and cab[8:12] == b"WEBP"
    elif firma == "wav":
        ok = cab[:4] == b"RIFF" and cab[8:12] == b"WAVE"
    elif firma == "avi":
        ok = cab[:4] == b"RIFF" and cab[8:12] == b"AVI "
    elif firma == "bmp":
        ok = cab[:2] == b"BM"
    elif firma == "ico":
        ok = cab[:4] == b"\x00\x00\x01\x00"
    elif firma == "tiff":
        ok = cab[:4] in {b"II*\x00", b"MM\x00*"}
    elif firma == "psd":
        ok = cab.startswith(b"8BPS")
    elif firma == "ftyp":  # mp4/m4v/mov/3gp/heic/avif/m4a
        ok = cab[4:8] == b"ftyp"
    elif firma == "ebml":  # webm/mkv/mka
        ok = cab.startswith(b"\x1a\x45\xdf\xa3")
    elif firma == "ogg":
        ok = cab.startswith(b"OggS")
    elif firma == "flac":
        ok = cab.startswith(b"fLaC")
    elif firma == "aac":
        ok = cab.startswith(b"ADIF") or cab[:2] in {b"\xff\xf1", b"\xff\xf9"}
    elif firma == "mid":
        ok = cab.startswith(b"MThd")
    elif firma == "mp3":
        ok = (cab.startswith(b"ID3")
              or (len(cab) >= 2 and cab[0] == 0xFF and (cab[1] & 0xE0) == 0xE0))
    elif firma == "mpeg":  # MPEG video (program/stream)
        ok = cab.startswith(b"\x00\x00\x01\xba") or cab.startswith(b"\x00\x00\x01\xb3")
    elif firma == "flv":
        ok = cab.startswith(b"FLV")
    elif firma == "asf":  # wma/wmv (ASF)
        ok = cab.startswith(b"\x30\x26\xb2\x75\x8e\x66\xcf\x11")
    elif firma == "swf":
        ok = cab[:3] in {b"FWS", b"CWS"}
    elif firma == "exe":
        ok = cab.startswith(b"MZ")
    elif firma == "rtf":
        ok = cab.startswith(b"{\\rtf")
    elif firma == "ics":
        ok = cab[:15].upper().startswith(b"BEGIN:VCALENDAR")
    elif firma == "json":
        return _verificar_json(ruta)
    elif firma == "xml":
        texto = cab.lstrip()
        ok = texto.startswith(b"<?xml") or texto.startswith(b"<")
    elif firma == "svg":
        return _verificar_svg(ruta)
    elif firma in {None, "texto"}:
        return _verificar_texto_plano(ruta)
    else:  # firma sin implementar: solo anti-HTML
        return _verificar_texto_plano(ruta)
    if not ok:
        return False, f"firma:no_es_{firma}"
    return True, "ok"


def _leer_texto(ruta: Path, limite: int = 4096) -> str:
    with open(ruta, "rb") as fh:
        datos = fh.read(limite)
    return datos.decode("utf-8", errors="replace").lstrip("\ufeff \t\r\n")


def _parece_html(texto: str) -> bool:
    inicio = texto[:200].lower()
    return inicio.startswith("<!doctype html") or inicio.startswith("<html")


def _verificar_texto_plano(ruta: Path):
    texto = _leer_texto(ruta)
    if _parece_html(texto):
        return False, "parece_html"
    return True, "ok"


def _verificar_json(ruta: Path):
    try:
        with open(ruta, "rb") as fh:
            json.loads(fh.read().decode("utf-8-sig"))
        return True, "ok"
    except (ValueError, UnicodeDecodeError):
        return False, "json_invalido"


def _verificar_svg(ruta: Path):
    texto = _leer_texto(ruta)
    if _parece_html(texto):
        return False, "parece_html"
    if "<svg" not in texto[:4000].lower():
        return False, "no_es_svg"
    return True, "ok"


def validar_archivo(ruta: Path, firma: str | None, expected_sha256: str | None = None):
    """(valido, motivo). Firma de bytes + hash opcional. Rechaza HTML
    disfrazado de archivo y copias locales alteradas."""
    valido, motivo = verificar_firma(ruta, firma)
    if not valido:
        return valido, motivo
    if expected_sha256:
        real = sha256_archivo(ruta)
        if real.lower() != expected_sha256.lower():
            return False, "hash_mismatch"
    return True, "ok"


# --------------------------------------------------------------------------- #
# Utilidades puras (sin red): se pueden probar de forma aislada.
# --------------------------------------------------------------------------- #
def normalizar_sitio(url: str) -> str:
    """Devuelve la URL canonica sin query/fragment y sin userinfo.

    Preserva subdirectorios para poder descubrir instalaciones en /blog o
    paginas interiores antes de resolver la raiz REST real.
    """
    return _normalizar_url(url)


def origen_sitio(url: str) -> str:
    partes = urlparse(_normalizar_url(url))
    return urlunparse((partes.scheme, partes.netloc, "", "", "", ""))


def api_base(site: str) -> str:
    return normalizar_sitio(site).rstrip("/") + "/wp-json"


def ruta_media_api(site_o_base: str, rest_base: str = "media", media_id=None) -> str:
    base = _normalizar_url(site_o_base, conservar_query=True)
    ruta = f"/wp/v2/{rest_base}"
    if media_id is not None:
        ruta += f"/{media_id}"
    partes = urlparse(base)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    if "rest_route" in query:
        query["rest_route"] = ruta
        return urlunparse(partes._replace(query=urlencode(query, safe="/")))
    if partes.path.rstrip("/").endswith("/wp-json"):
        return base.rstrip("/") + ruta
    return base.rstrip("/") + "/wp-json" + ruta


def ruta_coleccion_api(site_o_base: str, ruta_recurso: str) -> str:
    """Construye la URL de una coleccion REST arbitraria ('wp/v2/posts',
    'wc/v3/products', ...) sobre la raiz descubierta, respetando rest_route."""
    ruta = "/" + ruta_recurso.strip("/")
    if not re.fullmatch(r"/[A-Za-z0-9_.\-/]+", ruta) or ".." in ruta.split("/"):
        raise ValueError(f"Ruta de recurso invalida: {ruta_recurso!r}")
    base = _normalizar_url(site_o_base, conservar_query=True)
    partes = urlparse(base)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    if "rest_route" in query:
        query["rest_route"] = ruta
        return urlunparse(partes._replace(query=urlencode(query, safe="/")))
    if partes.path.rstrip("/").endswith("/wp-json"):
        return base.rstrip("/") + ruta
    return base.rstrip("/") + "/wp-json" + ruta


def sanitizar_nombre(texto: str, max_len: int = 80) -> str:
    """Nombre de archivo seguro: sin rutas, sin caracteres reservados."""
    limpio = re.sub(r"[^\w.\- ]+", "-", (texto or "").strip(), flags=re.UNICODE)
    limpio = re.sub(r"[\s_]+", "-", limpio).strip("-.")
    limpio = re.sub(r"-{2,}", "-", limpio)
    return (limpio or "sin-titulo")[:max_len]


def sha256_archivo(ruta: Path) -> str:
    digest = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 256), b""):
            digest.update(bloque)
    return digest.hexdigest()


def contar_paginas(ruta: Path):
    try:
        from pypdf import PdfReader  # dependencia opcional

        return len(PdfReader(str(ruta)).pages)
    except Exception:
        return None


def requiere_confirmacion(a_descargar: int, umbral: int, confirmo=None) -> bool:
    """Freno de volumen: por encima del umbral hay que repetir el numero exacto.

    No es una autorizacion institucional: es obligarte a mirar el costo del
    preflight antes de bajarlo, escribiendo el numero que viste.
    """
    if a_descargar <= umbral:
        return False
    try:
        return int(confirmo) != int(a_descargar)
    except (TypeError, ValueError):
        return True


def resumen_preflight(cliente, registros: list[dict], consulta: str = "") -> dict:
    """Informe previo: cuantos materiales hay, cuantos se bajaran y cuanto pesan."""
    tamanos = [r.get("bytes_api") for r in registros if r.get("bytes_api")]
    total = getattr(cliente, "total_disponible", None)
    return {
        "sitio": cliente.site,
        "consulta": consulta,
        "total_disponible": total,
        "a_descargar": len(registros),
        "bytes_conocidos": sum(int(t) for t in tamanos),
        "sin_tamano": len(registros) - len(tamanos),
        "muestra": [
            {"id": r.get("id"), "titulo": (r.get("titulo") or "")[:70],
             "bytes": r.get("bytes_api")}
            for r in registros[:5]
        ],
    }


def permite_robots(texto: str, ruta: str, agente: str = "*") -> bool:
    """Lee robots.txt de forma conservadora: aplica el bloque de nuestro agente
    y cae al bloque '*' cuando no hay reglas propias."""
    if not texto:
        return True
    grupos: dict[str, list[str]] = {}
    agentes_actuales: list[str] = []
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        campo, _, valor = linea.partition(":")
        campo, valor = campo.strip().lower(), valor.strip()
        if campo == "user-agent":
            agentes_actuales = [valor.lower()]
            grupos.setdefault(valor.lower(), [])
        elif campo == "disallow" and agentes_actuales:
            for ag in agentes_actuales:
                grupos.setdefault(ag, []).append(valor)
    agente_lc = agente.lower()
    reglas = grupos.get(agente_lc) or grupos.get("*") or []
    for regla in reglas:
        if regla and ruta.startswith(regla):
            return False
    return True


def upsert_manifest(filas, nuevas):
    """Fusiona por (sitio, id) conservando registros de otros sitios."""
    clave = lambda r: (str(r.get("sitio", "")), key_of(r))
    indice = {}
    orden = []
    for fila in list(filas):
        k = clave(fila)
        if k not in indice:
            orden.append(k)
        indice[k] = fila
    for fila in nuevas:
        k = clave(fila)
        if k not in indice:
            orden.append(k)
        indice[k] = fila
    return [indice[k] for k in orden]


def key_of(registro: dict) -> str:
    return str(registro.get("id") or registro.get("archivo") or "")


def fila_manifest(registro: dict, **extra) -> dict:
    fila = {c: "" for c in MANIFEST_COLUMNS}
    fila.update({k: v for k, v in registro.items() if k in MANIFEST_COLUMNS})
    fila.update(extra)
    return fila


def leer_manifest(ruta: Path) -> list[dict]:
    ruta = Path(ruta)
    if not ruta.is_file():
        return []
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def escribir_manifest(filas: list[dict], ruta: Path) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        escritor = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS, extrasaction="ignore")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in MANIFEST_COLUMNS})


def ahora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _segmento_uploads(url_media: str) -> str:
    """Extrae '2024/10' de una ruta wp-content/uploads/2024/10/..."""
    m = re.search(r"/uploads/(\d{4}/\d{2})/", url_media or "")
    return m.group(1) if m else "sin-fecha"


# --------------------------------------------------------------------------- #
# Cliente HTTP
# --------------------------------------------------------------------------- #
@dataclass
class ClienteWP:
    site: str
    pausa: float = PAUSA
    timeout: float = TIMEOUT
    session: requests.Session = field(default_factory=requests.Session)
    ultimo: float = 0.0
    total_disponible: int | None = None
    api_base: str | None = None
    api_indice: str | None = None
    api_fuente: str | None = None

    def __post_init__(self):
        self.site = _normalizar_url(self.site, conservar_query=True)
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    def _esperar(self):
        delta = time.time() - self.ultimo
        if delta < self.pausa:
            time.sleep(self.pausa - delta)
        self.ultimo = time.time()

    @staticmethod
    def _espera_reintentar(resp, intento: int) -> float | None:
        """Segundos a esperar antes de reintentar una lectura transitoria.

        Respeta Retry-After cuando es razonable; un valor mayor que el tope
        devuelve None: el error se informa en vez de esperar indefinidamente.
        """
        crudo = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
        espera = None
        if crudo:
            try:
                espera = float(crudo)
            except ValueError:
                espera = None  # fechas HTTP: no calcularlas, usar backoff corto
        base = float([1.0, 2.0][min(intento, 1)])
        espera = max(espera or 0.0, base)
        return espera if espera <= REINTENTO_TOPE_S else None

    def _get_con_reintentos(self, url: str, **kwargs):
        """GET de solo lectura con hasta REINTENTOS_MAX reintentos ante
        429/5xx/errores de red. Nunca se usa para escrituras."""
        intento = 0
        while True:
            self._esperar()
            try:
                resp = self.session.get(_validar_url_publica(url), timeout=self.timeout,
                                        allow_redirects=False, **kwargs)
            except requests.RequestException:
                if intento >= REINTENTOS_MAX:
                    raise
                time.sleep(float([1.0, 2.0][min(intento, 1)]))
                intento += 1
                continue
            if resp.status_code == 429 or resp.status_code >= 500:
                if intento >= REINTENTOS_MAX:
                    return resp
                espera = self._espera_reintentar(resp, intento)
                if espera is None:
                    return resp
                time.sleep(espera)
                intento += 1
                continue
            return resp

    def get_json(self, url: str, params: dict | None = None):
        """Devuelve (cuerpo, respuesta). Lanza en errores HTTP."""
        resp = self._get_con_reintentos(url, params=params)
        if resp.status_code in REDIRECCIONES_HTTP:
            raise requests.HTTPError("Redireccion de API: redescubrir antes de consultar", response=resp)
        resp.raise_for_status()
        return resp.json(), resp

    def _responder_descubrimiento(self, info: dict) -> dict:
        info.setdefault("site", self.site)
        info.setdefault("url_inicio", self.site)
        info.setdefault("api_base", None)
        info.setdefault("indice_url", None)
        info.setdefault("fuente", None)
        info.setdefault("nombre", None)
        info.setdefault("descripcion", None)
        info.setdefault("namespaces", [])
        info.setdefault("routes", [])
        info.setdefault("rutas_clave", {})
        info.setdefault("authentication", None)
        info.setdefault("cabeceras", {})
        info.setdefault("intentos", [])
        return info

    def _probar_indice(self, indice_url: str, fuente: str, restantes: int = 5) -> dict:
        try:
            self._esperar()
            resp = self.session.get(indice_url, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            return self._responder_descubrimiento({
                "ok": False,
                "error": "red",
                "detalle": str(exc),
                "indice_url": indice_url,
                "fuente": fuente,
            })

        status = resp.status_code
        tipo = (resp.headers.get("content-type") or "").lower()
        if status in (401, 403):
            return self._responder_descubrimiento({
                "ok": False,
                "error": f"http_{status}",
                "status": status,
                "content_type": tipo,
                "indice_url": indice_url,
                "fuente": fuente,
                "detalle": resp.text,
                "cabeceras": {
                    "content-type": resp.headers.get("content-type"),
                    "location": resp.headers.get("location") or resp.headers.get("Location"),
                },
            })

        if status in REDIRECCIONES_HTTP:
            destino = _redirigir_seguro(indice_url, resp)
            if destino is not None and destino != indice_url and restantes > 0:
                intento = self._probar_indice(destino, fuente, restantes - 1)
                if intento.get("ok") or intento.get("error") in {"http_401", "http_403"}:
                    return intento
            return self._responder_descubrimiento({
                "ok": False,
                "error": "red",
                "status": status,
                "content_type": tipo,
                "indice_url": indice_url,
                "fuente": fuente,
                "detalle": resp.text,
                "cabeceras": {
                    "content-type": resp.headers.get("content-type"),
                    "location": resp.headers.get("location") or resp.headers.get("Location"),
                },
            })

        try:
            cuerpo = resp.json()
        except ValueError:
            cuerpo = None

        if status == 200 and _indice_api_valido(cuerpo):
            rutas = sorted((cuerpo.get("routes") or {}).keys())
            api_base_desc = _base_indice_api(indice_url)
            return self._responder_descubrimiento({
                "ok": True,
                "site": self.site,
                "url_inicio": self.site,
                "indice_url": indice_url,
                "api_base": api_base_desc,
                "fuente": fuente,
                "status": status,
                "content_type": tipo,
                "nombre": cuerpo.get("name"),
                "descripcion": cuerpo.get("description"),
                "namespaces": cuerpo.get("namespaces", []),
                "routes": rutas,
                "rutas_clave": {
                    "media": "/wp/v2/media" if "/wp/v2/media" in rutas else None,
                    "posts": "/wp/v2/posts" if "/wp/v2/posts" in rutas else None,
                    "pages": "/wp/v2/pages" if "/wp/v2/pages" in rutas else None,
                },
                "authentication": cuerpo.get("authentication"),
                "cabeceras": {
                    "content-type": resp.headers.get("content-type"),
                    "x-wp-total": resp.headers.get("x-wp-total"),
                    "x-wp-totalpages": resp.headers.get("x-wp-totalpages"),
                },
            })

        if status == 200:
            return self._responder_descubrimiento({
                "ok": False,
                "error": "indice_invalido",
                "status": status,
                "content_type": tipo,
                "indice_url": indice_url,
                "fuente": fuente,
                "detalle": "respuesta no es un indice REST valido",
                "cabeceras": {
                    "content-type": resp.headers.get("content-type"),
                },
            })

        return self._responder_descubrimiento({
            "ok": False,
            "error": "red" if status == 429 or status >= 500 else "ausencia_api",
            "status": status,
            "content_type": tipo,
            "indice_url": indice_url,
            "fuente": fuente,
            "detalle": resp.text,
            "cabeceras": {
                "content-type": resp.headers.get("content-type"),
                "location": resp.headers.get("location") or resp.headers.get("Location"),
            },
        })

    def discover(self) -> dict:
        if _es_indice_rest(self.site):
            candidatos = [(self.site, "url_inicio")]
        else:
            candidatos = []
            try:
                self._esperar()
                raiz = self.session.get(self.site, timeout=self.timeout, allow_redirects=False)
            except requests.RequestException as exc:
                return self._responder_descubrimiento({
                    "ok": False,
                    "error": "red",
                    "detalle": str(exc),
                    "indice_url": self.site,
                    "fuente": "raiz",
                })

            if raiz is not None and raiz.status_code in (401, 403):
                return self._responder_descubrimiento({
                    "ok": False,
                    "error": f"http_{raiz.status_code}",
                    "status": raiz.status_code,
                    "content_type": (raiz.headers.get("content-type") or "").lower(),
                    "indice_url": raiz.url or self.site,
                    "fuente": "raiz",
                    "detalle": raiz.text,
                    "cabeceras": {
                        "content-type": raiz.headers.get("content-type"),
                        "location": raiz.headers.get("location") or raiz.headers.get("Location"),
                    },
                })

            if raiz is not None:
                if raiz.status_code in REDIRECCIONES_HTTP:
                    destino = _redirigir_seguro(self.site, raiz)
                    if destino:
                        try:
                            self._esperar()
                            raiz = self.session.get(destino, timeout=self.timeout, allow_redirects=False)
                        except requests.RequestException:
                            raiz = None

                if raiz is not None and raiz.status_code in (401, 403):
                    return self._responder_descubrimiento({
                        "ok": False,
                        "error": f"http_{raiz.status_code}",
                        "status": raiz.status_code,
                        "content_type": (raiz.headers.get("content-type") or "").lower(),
                        "indice_url": raiz.url or self.site,
                        "fuente": "raiz",
                        "detalle": raiz.text,
                        "cabeceras": {
                            "content-type": raiz.headers.get("content-type"),
                            "location": raiz.headers.get("location") or raiz.headers.get("Location"),
                        },
                    })

                if raiz is not None:
                    link_api = (
                        _extraer_link_api(raiz.headers.get("link") or raiz.headers.get("Link"), raiz.url or self.site)
                        or _extraer_link_api(raiz.text, raiz.url or self.site)
                    )
                    if link_api and _mismo_origen(raiz.url or self.site, link_api):
                        candidatos.append((link_api, "link"))

            for base in _ancestros_url(self.site):
                candidatos.append((f"{base.rstrip('/')}/wp-json/", "wp-json"))
                candidatos.append((f"{base.rstrip('/')}/?rest_route=/", "rest_route"))

        intentos = []
        primero_restringido = None
        primero_red = None
        primero_invalido = None
        primero_ausencia = None
        vistos = set()

        for indice_url, fuente in candidatos:
            if indice_url in vistos:
                continue
            vistos.add(indice_url)
            info = self._probar_indice(indice_url, fuente)
            intentos.append({k: info.get(k) for k in ("indice_url", "fuente", "status", "ok", "error")})
            if info.get("ok"):
                info["intentos"] = intentos
                self.api_base = info.get("api_base")
                self.api_indice = info.get("indice_url")
                self.api_fuente = info.get("fuente")
                return info
            if info.get("error") in {"http_401", "http_403"}:
                primero_restringido = primero_restringido or info
                break
            if info.get("error") == "red":
                primero_red = primero_red or info
            elif info.get("error") == "indice_invalido":
                primero_invalido = primero_invalido or info
            else:
                primero_ausencia = primero_ausencia or info

        fallo = primero_restringido or primero_red or primero_invalido or primero_ausencia or {
            "ok": False,
            "error": "ausencia_api",
            "site": self.site,
            "url_inicio": self.site,
            "detalle": "sin candidatos de descubrimiento",
        }
        fallo["ok"] = False
        fallo["intentos"] = intentos
        return self._responder_descubrimiento(fallo)

    def resolver_api(self) -> str:
        if self.api_base:
            return self.api_base
        info = self.discover()
        if not info.get("ok"):
            raise WpDiscoveryError(info)
        return self.api_base or info["api_base"]

    def robots(self) -> dict:
        resp = self.session.get(urljoin(origen_sitio(self.site) + "/", "robots.txt"), timeout=self.timeout)
        if resp.status_code != 200:
            return {"status": resp.status_code, "texto": "", "permite_uploads": None}
        texto = resp.text
        return {
            "status": resp.status_code,
            "texto": texto,
            "permite_uploads": permite_robots(texto, "/wp-content/uploads/"),
            "permite_rest": permite_robots(texto, "/wp-json/"),
        }

    # -- lectura de colecciones --------------------------------------------- #
    def _iterar_coleccion(self, url: str, params: dict, max_items=None, per_page=None):
        """Itera una coleccion REST paginada y devuelve (items, total, paginas).

        Las colecciones objeto (types, statuses, taxonomies) se devuelven
        como lista con cada clave envuelta: [{"__clave": nombre, ...valor}].
        Un dict con 'code' (error WP) lanza ValueError: no es coleccion vacia.
        """
        per_page = max(1, min(int(per_page or PER_PAGE_MAX), PER_PAGE_MAX))
        if max_items is not None:
            try:
                max_items = int(max_items)
            except (TypeError, ValueError):
                max_items = None
            if max_items and max_items > 0:
                per_page = min(per_page, max_items)
        pagina = 1
        vistos = 0
        items: list = []
        total = None
        paginas = None
        while True:
            consulta = dict(params)
            consulta["per_page"] = per_page
            consulta["page"] = pagina
            lote, resp = self.get_json(url, params=consulta)
            if isinstance(lote, dict) and not isinstance(lote, list):
                if "code" in lote:
                    # JSON de error WP: no confundirlo con coleccion vacia
                    raise ValueError(f"La coleccion {url} devolvio un error JSON: {lote.get('code')}")
                if pagina == 1:
                    # Coleccion objeto (types/statuses/taxonomies): envolver
                    # cada entrada con su clave para no perderla.
                    items = [{"__clave": clave, **valor} if isinstance(valor, dict) else {"__clave": clave, "valor": valor}
                             for clave, valor in lote.items()]
                break
            if not isinstance(lote, list):
                raise ValueError(f"La coleccion {url} no devolvio una lista JSON")
            if total is None:
                crudo = resp.headers.get("x-wp-total")
                total = int(crudo) if crudo is not None else None
            if not lote:
                break
            items.extend(lote)
            vistos += len(lote)
            if max_items and vistos >= max_items:
                items = items[:max_items]
                break
            total_paginas = int(resp.headers.get("x-wp-totalpages") or 1)
            paginas = total_paginas
            if pagina >= total_paginas:
                break
            pagina += 1
        return items, total, paginas or pagina

    def listar_media(self, mimes: list[str] | None = None, search=None,
                     per_page=PER_PAGE_MAX, max_items=None):
        """Itera los registros de media; mimes=None recorre todos los tipos."""
        api = self.resolver_api()
        params = {
            "orderby": "date",
            "order": "desc",
            "_fields": "id,date,slug,title,source_url,mime_type,media_details",
        }
        if mimes:
            params["mime_type"] = ",".join(mimes)
        if search:
            params["search"] = search
        items, total, _ = self._iterar_coleccion(ruta_media_api(api), params,
                                                 max_items=max_items, per_page=per_page)
        self.total_disponible = total
        for item in items:
            yield self._registro(item)

    def obtener_media(self, media_id) -> dict:
        """Objeto media individual por ID."""
        api = self.resolver_api()
        objeto, _ = self.get_json(ruta_media_api(api, media_id=media_id))
        if not isinstance(objeto, dict) or "id" not in objeto:
            raise ValueError(f"El ID {media_id} no devolvio un objeto media")
        return self._registro(objeto)

    def _registro(self, item: dict) -> dict:
        detalles = item.get("media_details") or {}
        api = self.api_base or api_base(normalizar_sitio(self.site))
        mime = normalizar_mime(item.get("mime_type")) or ""
        return {
            "sitio": self.site,
            "id": item.get("id"),
            "titulo": (item.get("title") or {}).get("rendered", ""),
            "slug": item.get("slug", ""),
            "fecha_media": item.get("date", ""),
            "mime_type": mime,
            "familia": familia_de_mime(mime),
            "url_media": item.get("source_url", ""),
            "url_api": ruta_media_api(api, media_id=item.get("id")),
            "bytes_api": detalles.get("filesize"),
        }

    # -- descarga de medios -------------------------------------------------- #
    def descargar_media(self, registro: dict, outdir: Path, sha_esperado: str | None = None) -> dict:
        """Descarga un archivo de la biblioteca validando content-type, firma
        de bytes y hash. Organiza por familia (documentos/imagenes/audio/
        video/datos/comprimidos/otros) y mes de subida."""
        try:
            url_media = _validar_url_publica(registro.get("url_media", ""), "URL de medio")
        except ValueError as exc:
            return {
                "estado": "error_url",
                "ruta": None,
                "fila": fila_manifest(registro, estado="error_url", motivo=str(exc), capturado_en_utc=ahora_utc()),
            }

        mime_esperado = normalizar_mime(registro.get("mime_type")) or None
        if not mime_esperado:  # sin mime informado: deducir desde la URL
            ext = extension_de_url(url_media)
            mime_esperado = EXT_A_MIME.get(ext)
        ext, familia, firma = resolver_destino(mime_esperado, url_media)

        outdir = Path(outdir)
        carpeta = outdir / familia / _segmento_uploads(url_media)
        carpeta.mkdir(parents=True, exist_ok=True)
        base = sanitizar_nombre(str(registro.get("id")))
        slug = sanitizar_nombre(registro.get("slug") or registro.get("titulo"))
        nombre = f"{base}.{ext}" if slug == base else f"{base}-{slug}.{ext}"
        destino = carpeta / nombre

        if destino.is_file() and sha_esperado:
            valido, _ = validar_archivo(destino, firma, sha_esperado)
            if valido:
                fila = fila_manifest(registro, archivo=str(destino), sha256=sha_esperado,
                                     bytes=destino.stat().st_size, estado="reutilizado",
                                     motivo="hash_coincide",
                                     paginas=contar_paginas(destino) if ext == "pdf" else "",
                                     capturado_en_utc=ahora_utc())
                return {"estado": "reutilizado", "ruta": destino, "fila": fila}

        intento = 0
        while True:
            try:
                resp = self._get_con_reintentos(url_media, stream=True)
                if resp.status_code in REDIRECCIONES_HTTP:
                    destino_redir = _redirigir_seguro(url_media, resp)
                    if not destino_redir:
                        return {"estado": "error_http", "ruta": None,
                                "fila": fila_manifest(registro, estado="error_http",
                                                      motivo=f"http_{resp.status_code}",
                                                      capturado_en_utc=ahora_utc())}
                    resp = self._get_con_reintentos(destino_redir, stream=True)
                if resp.status_code != 200:
                    return {"estado": "error_http", "ruta": None,
                            "fila": fila_manifest(registro, estado="error_http",
                                                  motivo=f"http_{resp.status_code}",
                                                  capturado_en_utc=ahora_utc())}
                tipo = resp.headers.get("content-type")
                if not tipo_contenido_aceptable(tipo, mime_esperado):
                    return {"estado": "tipo_inesperado", "ruta": None,
                            "fila": fila_manifest(registro, estado="tipo_inesperado",
                                                  motivo=f"content_type:{normalizar_mime(tipo) or 'desconocido'}",
                                                  capturado_en_utc=ahora_utc())}

                parcial = destino.with_suffix(f".{ext}.part")
                digest = hashlib.sha256()
                with open(parcial, "wb") as fh:
                    for bloque in resp.iter_content(chunk_size=1024 * 128):
                        if bloque:
                            digest.update(bloque)
                            fh.write(bloque)
                parcial.replace(destino)
                break
            except requests.RequestException:
                destino.with_suffix(f".{ext}.part").unlink(missing_ok=True)
                if intento >= REINTENTOS_MAX:
                    return {"estado": "error_http", "ruta": None,
                            "fila": fila_manifest(registro, estado="error_http",
                                                  motivo="red_interrumpida",
                                                  capturado_en_utc=ahora_utc())}
                intento += 1

        valido, motivo = validar_archivo(destino, firma)
        if not valido:
            destino.unlink(missing_ok=True)
            return {"estado": "invalido", "ruta": None,
                    "fila": fila_manifest(registro, estado="invalido", motivo=motivo,
                                          capturado_en_utc=ahora_utc())}

        fila = fila_manifest(
            registro,
            archivo=str(destino),
            bytes=destino.stat().st_size,
            sha256=digest.hexdigest(),
            paginas=contar_paginas(destino) if ext == "pdf" else "",
            estado="descargado",
            motivo="ok",
            capturado_en_utc=ahora_utc(),
        )
        return {"estado": "descargado", "ruta": destino, "fila": fila}


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
def _tamano_remoto(cliente, url: str):
    """Content-Length del recurso, para el preflight de una URL suelta."""
    try:
        cliente._esperar()
        resp = cliente.session.head(url, timeout=cliente.timeout, allow_redirects=False)
        if resp.status_code in REDIRECCIONES_HTTP:
            destino = _redirigir_seguro(url, resp)
            if destino:
                cliente._esperar()
                resp = cliente.session.head(destino, timeout=cliente.timeout, allow_redirects=False)
        largo = resp.headers.get("content-length")
        return int(largo) if largo and largo.isdigit() else None
    except Exception:
        return None


def _resumen_desde_filas(filas: list[dict]) -> dict:
    est = {}
    for fila in filas:
        est[fila.get("estado", "")] = est.get(fila.get("estado", ""), 0) + 1
    return est


def _registro_desde_url(cli, url_media: str, args_id) -> dict:
    """Registro sintetico para descargar una URL directa de cualquier tipo."""
    ext = extension_de_url(url_media)
    mime = EXT_A_MIME.get(ext)
    tamano = _tamano_remoto(cli, url_media)
    base = sanitizar_nombre(Path(urlparse(url_media).path).stem)
    return {"sitio": cli.site, "id": args_id or base,
            "titulo": base, "slug": base,
            "fecha_media": _segmento_uploads(url_media), "mime_type": mime or "",
            "url_media": url_media, "url_api": "", "bytes_api": tamano}


def cmd_discover(args) -> int:
    cli = ClienteWP(args.site)
    info = cli.discover()
    if not info.get("ok"):
        raise WpDiscoveryError(info)
    response = {"discover": info, "robots": cli.robots(), "tls": TLS_FUENTE}
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def cmd_robots(args) -> int:
    cli = ClienteWP(args.site)
    print(json.dumps(cli.robots(), ensure_ascii=False, indent=2))
    return 0


def cmd_media(args) -> int:
    mimes = resolver_mimes(args.mime)
    cli = ClienteWP(args.site, pausa=getattr(args, "sleep", PAUSA))
    registros = list(cli.listar_media(mimes=mimes, search=args.search,
                                      per_page=args.per_page, max_items=args.max))
    print(json.dumps({"total_disponible": cli.total_disponible,
                      "filtros": {"mime": args.mime or None, "search": args.search or None},
                      "total_listado": len(registros), "registros": registros},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_preflight(args) -> int:
    """Solo informa: no descarga nada."""
    mimes = resolver_mimes(args.mime)
    cli = ClienteWP(args.site, pausa=getattr(args, "sleep", PAUSA))
    registros = list(cli.listar_media(mimes=mimes, search=args.search,
                                      per_page=args.per_page, max_items=args.max))
    resumen = resumen_preflight(cli, registros, consulta=f"mime={args.mime or 'todos'} search={args.search or ''}".strip())
    resumen["umbral_confirmacion"] = args.umbral
    resumen["requiere_confirmacion"] = requiere_confirmacion(len(registros), args.umbral)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


def cmd_download(args) -> int:
    mimes = resolver_mimes(args.mime)
    cli = ClienteWP(args.site, pausa=args.sleep)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.csv"
    previas = leer_manifest(manifest_path)
    por_clave = {(f.get("sitio"), str(f.get("id") or "")): f for f in previas}

    if args.url:
        url_media = _validar_url_publica(args.url, "URL de medio")
        registros = [_registro_desde_url(cli, url_media, args.id)]
    elif args.id:
        registros = [cli.obtener_media(args.id)]
    else:
        registros = list(cli.listar_media(mimes=mimes, search=args.search,
                                          per_page=args.per_page, max_items=args.max))

    resumen = resumen_preflight(cli, registros,
                                consulta=f"mime={args.mime or 'todos'} search={args.search or ''}".strip()
                                or args.url or "")
    resumen["umbral_confirmacion"] = args.umbral
    print(json.dumps({"preflight": resumen}, ensure_ascii=False), file=sys.stderr)

    if requiere_confirmacion(len(registros), args.umbral, args.confirmo_bajar):
        print(json.dumps({
            "error": "requiere_confirmacion",
            "a_descargar": len(registros),
            "umbral": args.umbral,
            "instruccion": ("Nada se descargo. Revisar el preflight y repetir con "
                            f"--confirmo-bajar {len(registros)} para bajar ese lote exacto."),
        }, ensure_ascii=False), file=sys.stderr)
        return 3

    guardadas = []
    for registro in registros:
        clave = (registro["sitio"], str(registro["id"]))
        sha_previo = por_clave.get(clave, {}).get("sha256") or None
        resultado = cli.descargar_media(registro, out, sha_esperado=sha_previo)
        print(f"[{resultado['estado']}] id={registro['id']} {registro.get('titulo','')[:60]}", file=sys.stderr)
        guardadas.append(resultado["fila"])

    filas = upsert_manifest(previas, guardadas)
    escribir_manifest(filas, manifest_path)
    resumen = _resumen_desde_filas(filas)
    print(json.dumps({"manifest": str(manifest_path), "nuevas": len(guardadas),
                      "resumen": resumen}, ensure_ascii=False, indent=2))
    return 0 if not any(e in resumen for e in ESTADOS_FALLO) else 1


def _resolver_recurso(recurso: str) -> str:
    """Nombre corto o ruta relativa -> ruta REST (sin raiz)."""
    texto = (recurso or "").strip().strip("/")
    if not texto:
        raise ValueError("Falta --recurso (posts, pages, media, categories, tags, users, comments, ...)")
    if texto in RECURSOS_EXPORT:
        return RECURSOS_EXPORT[texto]
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*", texto) or ".." in texto.split("/"):
        raise ValueError(f"Recurso invalido: {recurso!r}. Usar un atajo o una ruta relativa como 'wp/v2/posts'")
    return texto


def _nombre_export(ruta: str, filtros: dict, campos: str | None, id_objeto, formato: str) -> tuple[str, str]:
    """(id de manifiesto, nombre de archivo) estables para una exportacion.

    El ID del objeto ya queda en la ruta; solo filtros y campos generan la
    huella que distingue capturas distintas del mismo recurso. La huella usa
    una cadena canonica compartida con el CLI R: el mismo filtro produce el
    mismo archivo y la misma fila de manifiesto en ambos lenguajes.
    """
    base = ruta.strip("/").replace("/", "-")
    carga = f"campos={campos or ''}"
    if filtros:
        carga += "|" + "&".join(f"{k}={filtros[k]}" for k in sorted(filtros))
    huella = hashlib.sha256(carga.encode("utf-8")).hexdigest()[:8] if (filtros or campos) else ""
    ident = f"export:{ruta.strip('/')}" + (f"#{huella}" if huella else "")
    nombre = base + (f"-{huella}" if huella else "") + f".{formato}"
    return ident, nombre


def cmd_export(args) -> int:
    cli = ClienteWP(args.site, pausa=args.sleep)
    out = Path(args.out)
    carpeta = out / "json"
    carpeta.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.csv"
    previas = leer_manifest(manifest_path)

    ruta = _resolver_recurso(args.recurso)
    if args.id:
        ruta = f"{ruta}/{args.id}"

    filtros: dict[str, str] = {}
    for par in args.filtro or []:
        clave, sep, valor = par.partition("=")
        if not sep or not clave or not valor:
            raise ValueError(f"--filtro espera clave=valor, recibido: {par!r}")
        filtros[clave] = valor
    if args.search:
        filtros["search"] = args.search
    params: dict[str, str] = dict(filtros)
    if args.campos:
        params["_fields"] = args.campos

    api = cli.resolver_api()
    url = ruta_coleccion_api(api, ruta)

    per_page_efectiva = max(1, min(int(args.per_page), PER_PAGE_MAX))
    solicitudes = 1 if args.id else max(1, -(-int(args.max) // per_page_efectiva))
    resumen = {
        "sitio": cli.site,
        "recurso": ruta,
        "max_items": None if args.id else int(args.max),
        "solicitudes_estimadas": solicitudes,
        "umbral_confirmacion": args.umbral,
    }
    print(json.dumps({"preflight": resumen}, ensure_ascii=False), file=sys.stderr)
    if requiere_confirmacion(solicitudes, args.umbral, args.confirmo_bajar):
        print(json.dumps({
            "error": "requiere_confirmacion",
            "solicitudes_estimadas": solicitudes,
            "umbral": args.umbral,
            "instruccion": ("Nada se exporto. Revisar el preflight y repetir con "
                            f"--confirmo-bajar {solicitudes} para ese alcance exacto."),
        }, ensure_ascii=False), file=sys.stderr)
        return 3
    if args.id:
        objeto, resp = cli.get_json(url, params=params or None)
        if not isinstance(objeto, dict):
            raise ValueError(f"{url} no devolvio un objeto JSON")
        items = [objeto]
        total, paginas = None, None
    else:
        items, total, paginas = cli._iterar_coleccion(url, params, max_items=args.max, per_page=args.per_page)


    ident, nombre = _nombre_export(ruta, filtros, args.campos, args.id, args.formato)
    destino = carpeta / nombre
    if args.formato == "ndjson":
        with open(destino, "w", encoding="utf-8", newline="\n") as fh:
            for item in items:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    else:
        envoltura = {
            "sitio": cli.site,
            "recurso": ruta,
            "ruta_api": url,
            "filtros": filtros,
            "campos": args.campos or None,
            "total_disponible": total,
            "paginas_recorridas": paginas,
            "items": items,
            "capturado_en_utc": ahora_utc(),
        }
        with open(destino, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(envoltura, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    digest = sha256_archivo(destino)
    registro = {
        "sitio": cli.site, "id": ident, "titulo": f"Export {ruta}",
        "slug": nombre, "fecha_media": "", "mime_type": "application/json",
        "url_media": "", "url_api": url, "bytes_api": destino.stat().st_size,
    }
    fila = fila_manifest(registro, archivo=str(destino), bytes=destino.stat().st_size,
                         sha256=digest, paginas="", estado="exportado",
                         motivo=f"items:{len(items)}", capturado_en_utc=ahora_utc())
    filas = upsert_manifest(previas, [fila])
    escribir_manifest(filas, manifest_path)
    print(json.dumps({"archivo": str(destino), "items": len(items), "total_disponible": total,
                      "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))
    return 0


def _verificar_fila(fila: dict):
    ruta = Path(fila.get("archivo") or "")
    if ruta.suffix.lower() in {".json", ".ndjson"} or normalizar_mime(fila.get("mime_type")) == "application/json":
        if not ruta.is_file():
            return False, "sin_archivo"
        if ruta.suffix.lower() == ".ndjson":
            try:
                with open(ruta, encoding="utf-8") as fh:
                    lineas = [ln for ln in fh.read().splitlines() if ln.strip()]
                if not lineas:
                    return False, "archivo_vacio"
                for linea in lineas:
                    json.loads(linea)
            except (ValueError, UnicodeDecodeError):
                return False, "json_invalido"
        else:
            valido, motivo = verificar_firma(ruta, "json")
            if not valido:
                return valido, motivo
    else:
        mime = normalizar_mime(fila.get("mime_type"))
        ext = ruta.suffix.lstrip(".").lower()
        firma = firma_de_mime(mime)
        if firma is None and ext in EXT_A_MIME:
            firma = firma_de_mime(EXT_A_MIME[ext])
        if ext == "pdf" and not mime:
            firma = "pdf"
        valido, motivo = verificar_firma(ruta, firma)
        if not valido:
            return valido, motivo
    if fila.get("sha256"):
        real = sha256_archivo(ruta)
        if real.lower() != fila["sha256"].lower():
            return False, "hash_mismatch"
    return True, "ok"


def cmd_verify(args) -> int:
    out = Path(args.out)
    manifest_path = out / "manifest.csv"
    filas = leer_manifest(manifest_path)
    if not filas:
        print(json.dumps({"manifest": str(manifest_path), "filas": 0, "error": "manifest_ausente"}))
        return 1
    verificadas = []
    for fila in filas:
        if fila.get("estado") in ESTADOS_OK and (fila.get("archivo") or "").strip():
            valido, motivo = _verificar_fila(fila)
        else:
            valido, motivo = False, "sin_archivo"
        verificadas.append({"id": fila.get("id"), "estado": fila.get("estado"),
                            "valido": valido, "motivo": motivo})
    ok = sum(1 for v in verificadas if v["valido"])
    print(json.dumps({"manifest": str(manifest_path), "filas": len(filas), "validas": ok,
                      "tls": TLS_FUENTE, "detalle": verificadas}, ensure_ascii=False, indent=2))
    return 0 if ok == len(filas) else 1


AYUDA_ALIAS = (
    "aliases de --mime (extension -> MIME): "
    + ", ".join(f"{ext}" for ext in sorted(EXT_A_MIME))
)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="API REST de WordPress: descarga verificada de medios (cualquier formato) y exportacion JSON",
        epilog=AYUDA_ALIAS, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    def con_sitio(p):
        p.add_argument("--site", required=True, help="URL base del sitio WordPress (ej. https://ejemplo.com)")

    p_disc = sub.add_parser("discover", help="Verifica /wp-json/ y endpoints disponibles")
    con_sitio(p_disc)
    p_disc.set_defaults(func=cmd_discover)

    p_rob = sub.add_parser("robots", help="Lee robots.txt y evalua /wp-content/uploads/ y /wp-json/")
    con_sitio(p_rob)
    p_rob.set_defaults(func=cmd_robots)

    p_med = sub.add_parser("media", help="Lista la biblioteca de medios, cualquier MIME")
    con_sitio(p_med)
    p_med.add_argument("--mime", default=None,
                       help="Filtro por MIME o alias separado por comas (pdf, jpg, mp4, application/json); sin valor = todos")
    p_med.add_argument("--search", default=None)
    p_med.add_argument("--per-page", type=int, default=100)
    p_med.add_argument("--max", type=int, default=None)
    p_med.add_argument("--sleep", type=float, default=PAUSA)
    p_med.set_defaults(func=cmd_media)

    p_pre = sub.add_parser("preflight", help="Informa cuantos archivos y cuantos bytes hay, sin descargar")
    con_sitio(p_pre)
    p_pre.add_argument("--mime", default=None)
    p_pre.add_argument("--search", default=None)
    p_pre.add_argument("--per-page", type=int, default=100)
    p_pre.add_argument("--max", type=int, default=UMBRAL_CONFIRMACION + 1)
    p_pre.add_argument("--umbral", type=int, default=UMBRAL_CONFIRMACION)
    p_pre.add_argument("--sleep", type=float, default=PAUSA)
    p_pre.set_defaults(func=cmd_preflight)

    p_dl = sub.add_parser("download", help="Descarga medios de cualquier formato y escribe manifest.csv")
    con_sitio(p_dl)
    p_dl.add_argument("--mime", default=None, help="Filtro por MIME o alias (pdf, jpg, mp4, zip, ...)")
    p_dl.add_argument("--url", default=None, help="URL directa a un archivo publico de cualquier tipo")
    p_dl.add_argument("--id", default=None, help="ID de un objeto media concreto")
    p_dl.add_argument("--search", default=None)
    p_dl.add_argument("--per-page", type=int, default=100)
    p_dl.add_argument("--max", type=int, default=3)
    p_dl.add_argument("--sleep", type=float, default=PAUSA)
    p_dl.add_argument("--out", default="datos")
    p_dl.add_argument("--umbral", type=int, default=UMBRAL_CONFIRMACION,
                      help="Cantidad a partir de la cual se exige --confirmo-bajar")
    p_dl.add_argument("--confirmo-bajar", type=int, default=None, metavar="N",
                      help="Repetir el numero exacto informado en el preflight")
    p_dl.set_defaults(func=cmd_download)

    p_exp = sub.add_parser("export", help="Exporta una coleccion REST a JSON/NDJSON verificado")
    con_sitio(p_exp)
    p_exp.add_argument("--recurso", required=True,
                       help="Atajo (posts, pages, media, categories, tags, users, comments, types, statuses, taxonomies, search, settings) o ruta relativa (wc/v3/products)")
    p_exp.add_argument("--id", default=None, help="Exportar un solo objeto por ID")
    p_exp.add_argument("--search", default=None)
    p_exp.add_argument("--filtro", action="append", default=None, metavar="CLAVE=VALOR",
                       help="Parametro de consulta de la coleccion; repetible (after=2024-01-01)")
    p_exp.add_argument("--campos", default=None, help="_fields del endpoint (id,title,date)")
    p_exp.add_argument("--formato", choices=("json", "ndjson"), default="json")
    p_exp.add_argument("--per-page", type=int, default=100)
    p_exp.add_argument("--max", type=int, default=100)
    p_exp.add_argument("--sleep", type=float, default=PAUSA)
    p_exp.add_argument("--out", default="datos")
    p_exp.add_argument("--umbral", type=int, default=UMBRAL_CONFIRMACION)
    p_exp.add_argument("--confirmo-bajar", type=int, default=None, metavar="N")
    p_exp.set_defaults(func=cmd_export)

    p_ver = sub.add_parser("verify", help="Revalida el manifest y los archivos en disco")
    p_ver.add_argument("--out", default="datos")
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv=None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.func(args)
    except WpDiscoveryError as exc:
        print(json.dumps({"error": "descubrimiento", "detalle": str(exc), "info": exc.info}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    except ValueError as exc:
        print(json.dumps({"error": "valor", "detalle": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except requests.HTTPError as exc:
        print(json.dumps({"error": "http", "detalle": str(exc),
                          "status": getattr(exc.response, "status_code", None)}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    except requests.RequestException as exc:
        print(json.dumps({"error": "red", "detalle": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
