"""Pruebas de wp_api.py sin red: utilidades puras y cliente con sesion falsa."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp_api  # noqa: E402


class FakeRespuesta:
    def __init__(self, status=200, headers=None, cuerpo=None, bloques=None, texto="", url="https://ejemplo.com/"):
        self.status_code = status
        self.headers = headers or {}
        self._cuerpo = cuerpo
        self._bloques = bloques or []
        self.text = texto
        self.url = url

    def json(self):
        return self._cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise wp_api.requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1024):
        yield from self._bloques


class FakeSesion:
    def __init__(self, respuestas=None):
        self.headers = {}
        self.respuestas = list(respuestas or [])
        self.llamadas = []

    def _siguiente(self, metodo, url, params=None, timeout=None, stream=False, allow_redirects=None):
        self.llamadas.append({"metodo": metodo, "url": url, "params": params, "stream": stream,
                             "allow_redirects": allow_redirects})
        if not self.respuestas:
            raise AssertionError(f"Sin respuesta preparada para {url}")
        resp = self.respuestas.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def get(self, url, params=None, timeout=None, stream=False, allow_redirects=False, **kwargs):
        return self._siguiente("GET", url, params=params, timeout=timeout, stream=stream,
                               allow_redirects=allow_redirects)

    def head(self, url, timeout=None, allow_redirects=False, **kwargs):
        return self._siguiente("HEAD", url, timeout=timeout, allow_redirects=allow_redirects)


def pdf_bytes(texto: bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n") -> bytes:
    return texto


class TestRegistroDeFormatos(unittest.TestCase):
    """El registro MIME mapea familia, extension y firma para cada formato."""

    def test_familias_cubren_los_formatos_de_wordpress(self):
        casos = {
            "application/pdf": "documentos",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "documentos",
            "image/jpeg": "imagenes",
            "image/svg+xml": "imagenes",
            "audio/mpeg": "audio",
            "video/mp4": "video",
            "application/zip": "comprimidos",
            "application/json": "datos",
            "text/csv": "datos",
            "application/x-shockwave-flash": "otros",
        }
        for mime, familia in casos.items():
            with self.subTest(mime=mime):
                self.assertEqual(wp_api.familia_de_mime(mime), familia)

    def test_familia_por_prefijo_para_mimes_no_registrados(self):
        self.assertEqual(wp_api.familia_de_mime("image/x-fancy"), "imagenes")
        self.assertEqual(wp_api.familia_de_mime("video/x-fancy"), "video")
        self.assertEqual(wp_api.familia_de_mime("audio/x-fancy"), "audio")
        self.assertEqual(wp_api.familia_de_mime("application/x-fancy"), "otros")

    def test_resolver_mimes_acepta_alias_y_mimes(self):
        self.assertEqual(wp_api.resolver_mimes("pdf"), ["application/pdf"])
        self.assertEqual(wp_api.resolver_mimes("pdf,jpg"),
                         ["application/pdf", "image/jpeg"])
        self.assertEqual(wp_api.resolver_mimes("application/pdf image/png"),
                         ["application/pdf", "image/png"])
        self.assertIsNone(wp_api.resolver_mimes(None))
        self.assertIsNone(wp_api.resolver_mimes("todos"))
        self.assertIsNone(wp_api.resolver_mimes("*"))

    def test_resolver_mimes_rechaza_desconocido(self):
        with self.assertRaises(ValueError):
            wp_api.resolver_mimes("docx2")

    def test_resolver_destino_prefiere_mime_y_cae_a_extension(self):
        self.assertEqual(wp_api.resolver_destino("application/pdf", "https://x/a.pdf"),
                         ("pdf", "documentos", "pdf"))
        # La extension de la URL respeta el alias del MIME informado
        self.assertEqual(wp_api.resolver_destino("image/jpeg", "https://x/a.jpeg"),
                         ("jpeg", "imagenes", "jpg"))
        # Sin MIME informado, deduce desde la extension de la URL
        self.assertEqual(wp_api.resolver_destino(None, "https://x/a.mp3"),
                         ("mp3", "audio", "mp3"))
        self.assertEqual(wp_api.resolver_destino(None, "https://x/archivo.rar"),
                         ("rar", "comprimidos", "rar"))
        # Desconocido total: binario en familia otros sin firma
        self.assertEqual(wp_api.resolver_destino(None, "https://x/archivo.zzz"),
                         ("zzz", "otros", None))

    def test_tipo_contenido_aceptable(self):
        self.assertTrue(wp_api.tipo_contenido_aceptable("application/pdf", "application/pdf"))
        self.assertTrue(wp_api.tipo_contenido_aceptable("application/pdf; charset=x", "application/pdf"))
        self.assertTrue(wp_api.tipo_contenido_aceptable("application/octet-stream", "application/pdf"))
        self.assertTrue(wp_api.tipo_contenido_aceptable("image/png", "image/png"))
        # Variante de la misma familia (audio/wav vs audio/x-wav)
        self.assertTrue(wp_api.tipo_contenido_aceptable("audio/x-wav", "audio/wav"))
        # HTML nunca es aceptable
        self.assertFalse(wp_api.tipo_contenido_aceptable("text/html", "application/pdf"))
        self.assertFalse(wp_api.tipo_contenido_aceptable("text/html; charset=UTF-8", None))
        # Familia distinta
        self.assertFalse(wp_api.tipo_contenido_aceptable("image/png", "application/pdf"))
        # Sin content-type servido: la firma de bytes decide
        self.assertTrue(wp_api.tipo_contenido_aceptable(None, "application/pdf"))


class TestFirmasDeFormato(unittest.TestCase):
    """Verificacion por bytes magicos de cada familia de formatos."""

    def _firmar(self, datos: bytes) -> Path:
        carpeta = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(carpeta, ignore_errors=True))
        ruta = carpeta / "firma.bin"
        ruta.write_bytes(datos)
        return ruta

    def test_firmas_validas(self):
        tar = bytearray(512)
        tar[257:262] = b"ustar"
        casos = {
            "pdf": b"%PDF-1.7\n%",
            "zip": b"PK\x03\x04\x14\x00",
            "7z": b"7z\xbc\xaf\x27\x1c\x00\x02",
            "rar": b"Rar!\x1a\x07\x01\x00",
            "gzip": b"\x1f\x8b\x08\x00\x00\x00\x00\x00",
            "tar": bytes(tar),
            "ole": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00",
            "png": b"\x89PNG\r\n\x1a\n\x00\x00",
            "jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF",
            "gif": b"GIF89a\x01\x00\x01\x00",
            "webp": b"RIFF\x24\x00\x00\x00WEBPVP8 ",
            "wav": b"RIFF\x24\x00\x00\x00WAVEfmt ",
            "avi": b"RIFF\x24\x00\x00\x00AVI LIST",
            "bmp": b"BM\x36\x00\x00\x00",
            "ico": b"\x00\x00\x01\x00\x01\x00",
            "tiff": b"II*\x00\x08\x00\x00\x00",
            "psd": b"8BPS\x00\x01\x00\x00\x00\x00",
            "ftyp": b"\x00\x00\x00\x20ftypisom\x00\x00",
            "ebml": b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01",
            "ogg": b"OggS\x00\x02\x00\x00\x00\x00",
            "flac": b"fLaC\x00\x00\x00\x22",
            "aac": b"ADIF\x00\x00",
            "mid": b"MThd\x00\x00\x00\x06",
            "mp3": b"ID3\x03\x00\x00\x00\x00\x00\x00",
            "mpeg": b"\x00\x00\x01\xba\x21",
            "flv": b"FLV\x01\x05\x00\x00",
            "asf": b"\x30\x26\xb2\x75\x8e\x66\xcf\x11",
            "swf": b"FWS\x06\x00\x00\x00",
            "exe": b"MZ\x90\x00\x03\x00",
            "rtf": b"{\\rtf1\\ansi}",
            "ics": b"BEGIN:VCALENDAR\r\nVERSION:2.0",
        }
        for firma, datos in casos.items():
            with self.subTest(firma=firma):
                valido, motivo = wp_api.verificar_firma(self._firmar(datos), firma)
                self.assertTrue(valido, motivo)

    def test_mp3_nudo_de_sincronizacion_sin_id3(self):
        valido, _ = wp_api.verificar_firma(self._firmar(b"\xff\xfb\x90\x44\x00"), "mp3")
        self.assertTrue(valido)

    def test_json_valido_e_invalido(self):
        self.assertEqual(wp_api.verificar_firma(self._firmar(b'{"a": [1, 2]}'), "json"), (True, "ok"))
        # BOM UTF-8 aceptado
        self.assertEqual(wp_api.verificar_firma(self._firmar(b'\xef\xbb\xbf{"a": 1}'), "json"), (True, "ok"))
        valido, motivo = wp_api.verificar_firma(self._firmar(b'{"a": [1,'), "json")
        self.assertFalse(valido)
        self.assertEqual(motivo, "json_invalido")

    def test_svg_valido_e_html_rechazado(self):
        self.assertEqual(wp_api.verificar_firma(self._firmar(b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>'), "svg"), (True, "ok"))
        valido, motivo = wp_api.verificar_firma(self._firmar(b"<html><body>403</body></html>"), "svg")
        self.assertFalse(valido)
        self.assertEqual(motivo, "parece_html")
        valido, motivo = wp_api.verificar_firma(self._firmar(b"no hay svg aqui"), "svg")
        self.assertEqual((valido, motivo), (False, "no_es_svg"))

    def test_formatos_sin_firma_rechazan_html(self):
        for firma in (None, "texto"):
            with self.subTest(firma=firma):
                valido, motivo = wp_api.verificar_firma(self._firmar(b"<!DOCTYPE html><html>x"), firma)
                self.assertFalse(valido)
                self.assertEqual(motivo, "parece_html")
                valido, _ = wp_api.verificar_firma(self._firmar(b"a,b\n1,2\n"), firma)
                self.assertTrue(valido)

    def test_firma_incorrecta_se_reporta(self):
        valido, motivo = wp_api.verificar_firma(self._firmar(b"%PDF-1.4\n"), "png")
        self.assertEqual((valido, motivo), (False, "firma:no_es_png"))
        valido, motivo = wp_api.verificar_firma(self._firmar(b"\x89PNG\r\n\x1a\n"), "pdf")
        self.assertEqual((valido, motivo), (False, "firma:no_es_pdf"))

    def test_archivo_vacio_y_ausente(self):
        ruta = self._firmar(b"")
        self.assertEqual(wp_api.verificar_firma(ruta, "pdf"), (False, "archivo_vacio"))
        self.assertEqual(wp_api.verificar_firma(Path(ruta.parent / "nada.bin"), "pdf"),
                         (False, "archivo_ausente"))

    def test_validar_archivo_agrega_hash(self):
        ruta = self._firmar(b"%PDF-1.4\ncontenido")
        sha = wp_api.sha256_archivo(ruta)
        self.assertEqual(wp_api.validar_archivo(ruta, "pdf", sha), (True, "ok"))
        self.assertEqual(wp_api.validar_archivo(ruta, "pdf", "0" * 64), (False, "hash_mismatch"))


class TestUtilidades(unittest.TestCase):
    def test_normalizar_sitio(self):
        self.assertEqual(wp_api.normalizar_sitio("ejemplo.com"), "https://ejemplo.com")
        self.assertEqual(wp_api.normalizar_sitio("https://ejemplo.com/"), "https://ejemplo.com")
        self.assertEqual(wp_api.normalizar_sitio("http://ejemplo.com/blog/a/b?x=1"), "http://ejemplo.com/blog/a/b")
        self.assertEqual(wp_api.normalizar_sitio("https://ejemplo.com/blog/"), "https://ejemplo.com/blog")
        with self.assertRaises(ValueError):
            wp_api.normalizar_sitio("")
        with self.assertRaises(ValueError):
            wp_api.normalizar_sitio("https://user:pass@ejemplo.com/blog")
        with self.assertRaises(ValueError):
            wp_api.normalizar_sitio("ftp://ejemplo.com/blog")

    def test_api_y_ruta_media(self):
        self.assertEqual(wp_api.api_base("https://ejemplo.com"), "https://ejemplo.com/wp-json")
        self.assertEqual(wp_api.ruta_media_api("https://ejemplo.com"), "https://ejemplo.com/wp-json/wp/v2/media")
        self.assertEqual(wp_api.ruta_media_api("https://ejemplo.com/blog/?rest_route=/"),
                         "https://ejemplo.com/blog/?rest_route=/wp/v2/media")
        self.assertEqual(
            wp_api.ruta_media_api("https://ejemplo.com/blog/?rest_route=/&lang=es", media_id=42),
            "https://ejemplo.com/blog/?rest_route=/wp/v2/media/42&lang=es",
        )

    def test_ruta_coleccion_api(self):
        self.assertEqual(wp_api.ruta_coleccion_api("https://ejemplo.com/wp-json", "wp/v2/posts"),
                         "https://ejemplo.com/wp-json/wp/v2/posts")
        self.assertEqual(wp_api.ruta_coleccion_api("https://ejemplo.com/blog/?rest_route=/", "wc/v3/products"),
                         "https://ejemplo.com/blog/?rest_route=/wc/v3/products")
        with self.assertRaises(ValueError):
            wp_api.ruta_coleccion_api("https://ejemplo.com/wp-json", "../wp/v2/admin")

    def test_sanitizar_nombre(self):
        self.assertEqual(wp_api.sanitizar_nombre("Silos granja y Distribución"), "Silos-granja-y-Distribución")
        self.assertEqual(wp_api.sanitizar_nombre("../../etc/passwd"), "etc-passwd")
        self.assertEqual(wp_api.sanitizar_nombre(""), "sin-titulo")
        self.assertLessEqual(len(wp_api.sanitizar_nombre("a" * 200)), 80)

    def test_permite_robots(self):
        yoast = "# START YOAST BLOCK\nUser-agent: *\nDisallow:\n\nSitemap: https://x/sitemap.xml\n"
        self.assertTrue(wp_api.permite_robots(yoast, "/wp-content/uploads/x.pdf"))
        bloqueado = "User-agent: *\nDisallow: /wp-content/uploads/\n"
        self.assertFalse(wp_api.permite_robots(bloqueado, "/wp-content/uploads/x.pdf"))
        self.assertTrue(wp_api.permite_robots(bloqueado, "/otra/ruta"))
        primero_agente = "User-agent: curso-bot\nDisallow: /wp-content/uploads/\n\nUser-agent: *\nDisallow:\n"
        self.assertTrue(wp_api.permite_robots(primero_agente, "/wp-content/uploads/x.pdf", agente="otro"))
        self.assertTrue(wp_api.permite_robots("", "/cualquier/cosa"))

    def test_segmento_uploads(self):
        self.assertEqual(wp_api._segmento_uploads("https://x/wp-content/uploads/2024/10/a.pdf"), "2024/10")
        self.assertEqual(wp_api._segmento_uploads("https://x/a.pdf"), "sin-fecha")

    def test_upsert_manifest_dedup_por_id(self):
        previas = [{"sitio": "https://a", "id": "1", "estado": "descargado"}]
        nuevas = [
            {"sitio": "https://a", "id": "1", "estado": "reutilizado"},
            {"sitio": "https://a", "id": "2", "estado": "descargado"},
            {"sitio": "https://b", "id": "1", "estado": "descargado"},
        ]
        combinado = wp_api.upsert_manifest(previas, nuevas)
        self.assertEqual(len(combinado), 3)
        porclave = {(f["sitio"], f["id"]): f["estado"] for f in combinado}
        self.assertEqual(porclave[("https://a", "1")], "reutilizado")
        self.assertEqual(porclave[("https://b", "1")], "descargado")

    def test_manifest_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = Path(td) / "manifest.csv"
            fila = wp_api.fila_manifest({"sitio": "https://a", "id": "5", "titulo": "Ünïcode, ok"},
                                        archivo="documentos/2024/10/5.pdf", estado="descargado")
            wp_api.escribir_manifest([fila], ruta)
            leido = wp_api.leer_manifest(ruta)
            self.assertEqual(len(leido), 1)
            self.assertEqual(leido[0]["titulo"], "Ünïcode, ok")
            self.assertEqual(list(leido[0].keys()), wp_api.MANIFEST_COLUMNS)
            self.assertEqual(wp_api.leer_manifest(Path(td) / "nada.csv"), [])


class TestClienteConSesionFalsa(unittest.TestCase):
    def _cliente(self, sesion, site="https://ejemplo.com"):
        return wp_api.ClienteWP(site=site, pausa=0.0, session=sesion)

    def test_registro_mapea_campos(self):
        cli = self._cliente(FakeSesion())
        reg = cli._registro({
            "id": 43887, "date": "2026-07-13T12:39:16", "slug": "catalogo",
            "title": {"rendered": "Catálogo SYMAGA"}, "mime_type": "application/pdf",
            "source_url": "https://www.ejemplo.com/wp-content/uploads/2024/10/a.pdf",
            "media_details": {"filesize": 123},
        })
        self.assertEqual(reg["id"], 43887)
        self.assertEqual(reg["titulo"], "Catálogo SYMAGA")
        self.assertEqual(reg["url_api"], "https://ejemplo.com/wp-json/wp/v2/media/43887")
        self.assertEqual(reg["familia"], "documentos")

    def test_listar_media_filtra_por_mimes_y_pagina(self):
        sesion = FakeSesion([
            FakeRespuesta(200, {"x-wp-totalpages": "2"},
                          [{"id": 1, "title": {"rendered": "a"}, "source_url": "https://e/a.pdf"},
                           {"id": 2, "title": {"rendered": "b"}, "source_url": "https://e/b.pdf"}]),
            FakeRespuesta(200, {"x-wp-totalpages": "2"},
                          [{"id": 3, "title": {"rendered": "c"}, "source_url": "https://e/c.pdf"}]),
        ])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        regs = list(cli.listar_media(mimes=["application/pdf", "image/jpeg"], max_items=2))
        self.assertEqual([r["id"] for r in regs], [1, 2])
        self.assertEqual(sesion.llamadas[0]["params"]["per_page"], 2)
        self.assertEqual(sesion.llamadas[0]["params"]["mime_type"], "application/pdf,image/jpeg")

    def test_listar_media_sin_filtro_no_envia_mime(self):
        sesion = FakeSesion([FakeRespuesta(200, {"x-wp-totalpages": "1"}, [])])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        list(cli.listar_media(max_items=1))
        self.assertNotIn("mime_type", sesion.llamadas[0]["params"])

    def test_obtener_media(self):
        sesion = FakeSesion([FakeRespuesta(200, cuerpo={
            "id": 7, "date": "2024-01-01T00:00:00", "slug": "foto", "title": {"rendered": "Foto"},
            "mime_type": "image/png", "source_url": "https://e/foto.png", "media_details": {"filesize": 9},
        })])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        reg = cli.obtener_media(7)
        self.assertEqual(reg["id"], 7)
        self.assertEqual(sesion.llamadas[0]["url"], "https://ejemplo.com/wp-json/wp/v2/media/7")

    def test_obtener_media_rechaza_respuesta_no_objeto(self):
        sesion = FakeSesion([FakeRespuesta(200, cuerpo=[{"id": 7}])])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        with self.assertRaises(ValueError):
            cli.obtener_media(7)

    def test_descargar_pdf_va_a_documentos(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "application/pdf"},
                                               bloques=[pdf_bytes()])])
            cli = self._cliente(sesion)
            reg = {"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                   "mime_type": "application/pdf",
                   "url_media": "https://ejemplo.com/wp-content/uploads/2024/10/a.pdf"}
            res = cli.descargar_media(reg, Path(td))
            self.assertEqual(res["estado"], "descargado")
            self.assertTrue(res["ruta"].is_file())
            self.assertEqual(res["ruta"].parent, Path(td) / "documentos" / "2024" / "10")
            self.assertEqual(res["ruta"].name, "9-t.pdf")
            self.assertEqual(res["fila"]["sha256"], hashlib.sha256(pdf_bytes()).hexdigest())

    def test_descargar_imagen_y_comprimido(self):
        png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xae\x42\x60\x82"
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([
                FakeRespuesta(200, {"content-type": "image/png"}, bloques=[png]),
                FakeRespuesta(200, {"content-type": "application/zip"}, bloques=[b"PK\x05\x06" + b"\x00" * 18]),
            ])
            cli = self._cliente(sesion)
            res_img = cli.descargar_media({"sitio": "https://ejemplo.com", "id": 21, "slug": "logo",
                                           "mime_type": "image/png",
                                           "url_media": "https://ejemplo.com/wp-content/uploads/2025/01/logo.png"},
                                          Path(td))
            res_zip = cli.descargar_media({"sitio": "https://ejemplo.com", "id": 22, "slug": "backup",
                                           "mime_type": "application/zip",
                                           "url_media": "https://ejemplo.com/wp-content/uploads/2025/01/backup.zip"},
                                          Path(td))
            self.assertEqual(res_img["estado"], "descargado")
            self.assertEqual(res_img["ruta"].parent, Path(td) / "imagenes" / "2025" / "01")
            self.assertEqual(res_img["ruta"].name, "21-logo.png")
            self.assertEqual(res_zip["estado"], "descargado")
            self.assertEqual(res_zip["ruta"].parent, Path(td) / "comprimidos" / "2025" / "01")

    def test_descargar_reutiliza_si_hash_coincide(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "application/pdf"},
                                               bloques=[pdf_bytes()])])
            cli = self._cliente(sesion)
            reg = {"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                   "mime_type": "application/pdf",
                   "url_media": "https://ejemplo.com/wp-content/uploads/2024/10/a.pdf"}
            primero = cli.descargar_media(reg, Path(td))
            sesion2 = FakeSesion()  # si intentara red, fallaria
            cli2 = self._cliente(sesion2)
            segundo = cli2.descargar_media(reg, Path(td), sha_esperado=primero["fila"]["sha256"])
            self.assertEqual(segundo["estado"], "reutilizado")
            self.assertEqual(sesion2.llamadas, [])

    def test_descargar_json_desde_url_sin_mime(self):
        payload = b'{"demo": true}'
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "application/json"},
                                               bloques=[payload])])
            cli = self._cliente(sesion)
            res = cli.descargar_media({"sitio": "https://ejemplo.com", "id": "datos", "slug": "datos",
                                       "url_media": "https://ejemplo.com/wp-content/uploads/2024/10/datos.json"},
                                      Path(td))
            self.assertEqual(res["estado"], "descargado")
            self.assertEqual(res["ruta"].parent, Path(td) / "datos" / "2024" / "10")
            self.assertEqual(res["ruta"].suffix, ".json")

    def test_descargar_html_con_content_type_html_es_tipo_inesperado(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "text/html; charset=UTF-8"},
                                               bloques=[b"<html>403</html>"])])
            cli = self._cliente(sesion)
            reg = {"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                   "mime_type": "application/pdf", "url_media": "https://ejemplo.com/x.pdf"}
            res = cli.descargar_media(reg, Path(td))
            self.assertEqual(res["estado"], "tipo_inesperado")
            self.assertIsNone(res["ruta"])
            self.assertIn("content_type:text/html", res["fila"]["motivo"])

    def test_descargar_html_disfrazado_de_pdf_es_invalido(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "application/pdf"},
                                               bloques=[b"<html>pagina de error</html>"])])
            cli = self._cliente(sesion)
            reg = {"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                   "mime_type": "application/pdf", "url_media": "https://ejemplo.com/x.pdf"}
            res = cli.descargar_media(reg, Path(td))
            self.assertEqual(res["estado"], "invalido")
            self.assertEqual(res["fila"]["motivo"], "firma:no_es_pdf")
            self.assertFalse((Path(td) / "documentos" / "sin-fecha" / "9-t.pdf").exists())

    def test_descargar_error_http(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(404, {"content-type": "text/html"})])
            cli = self._cliente(sesion)
            reg = {"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                   "mime_type": "application/pdf", "url_media": "https://ejemplo.com/x.pdf"}
            res = cli.descargar_media(reg, Path(td))
            self.assertEqual(res["estado"], "error_http")
            self.assertEqual(res["fila"]["motivo"], "http_404")

    def test_id_remoto_no_introduce_rutas(self):
        with tempfile.TemporaryDirectory() as td:
            sesion = FakeSesion([FakeRespuesta(200, {"content-type": "application/pdf"}, bloques=[pdf_bytes()])])
            cli = self._cliente(sesion)
            reg = {"id": "../escape", "slug": "demo", "mime_type": "application/pdf",
                   "url_media": "https://ejemplo.com/a.pdf"}
            resultado = cli.descargar_media(reg, Path(td))
            self.assertEqual(resultado["ruta"].parent, Path(td) / "documentos" / "sin-fecha")
            self.assertEqual(resultado["ruta"].read_bytes(), pdf_bytes())

    def test_redireccion_con_userinfo_no_envia_credenciales(self):
        sesion = FakeSesion([FakeRespuesta(302, {"location": "https://user:secret@ejemplo.com/wp-json/"})])
        info = self._cliente(sesion)._probar_indice("https://ejemplo.com/wp-json/", "test")
        self.assertFalse(info["ok"])
        self.assertEqual(len(sesion.llamadas), 1)

    def test_ciclo_de_redirecciones_termina(self):
        respuestas = [FakeRespuesta(302, {"location": f"/api/{i % 2}"}) for i in range(6)]
        sesion = FakeSesion(respuestas)
        info = self._cliente(sesion)._probar_indice("https://ejemplo.com/wp-json/", "test")
        self.assertFalse(info["ok"])
        self.assertEqual(info["error"], "red")

    def test_errores_transitorios_no_son_ausencia_api(self):
        for status in (429, 503):
            with self.subTest(status=status):
                sesion = FakeSesion([FakeRespuesta(status)])
                info = self._cliente(sesion)._probar_indice("https://ejemplo.com/wp-json/", "test")
                self.assertEqual(info["error"], "red")
                self.assertEqual(info["status"], status)

    def test_coleccion_invalida_no_parece_vacia(self):
        cli = self._cliente(FakeSesion([FakeRespuesta(200, cuerpo={"code": "error"})]))
        cli.api_base = "https://ejemplo.com/wp-json"
        with self.assertRaises(ValueError):
            list(cli.listar_media(max_items=1))

    def test_coleccion_objeto_se_envuelve_en_items(self):
        cuerpo = {"post": {"name": "post", "rest_base": "posts"}, "page": {"name": "page"}}
        cli = self._cliente(FakeSesion([FakeRespuesta(200, cuerpo=cuerpo)]))
        cli.api_base = "https://ejemplo.com/wp-json"
        items, total, _ = cli._iterar_coleccion("https://ejemplo.com/wp-json/wp/v2/types", {})
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["__clave"], "post")
        self.assertEqual(items[0]["rest_base"], "posts")

    def test_reintenta_lecturas_transitorias_y_respeta_retry_after(self):
        sesion = FakeSesion([
            FakeRespuesta(429, {"retry-after": "0"}),
            FakeRespuesta(200, {"content-type": "application/json"}, cuerpo=[]),
        ])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        with mock.patch("wp_api.time.sleep") as dormir:
            cuerpo, resp = cli.get_json("https://ejemplo.com/wp-json/wp/v2/posts")
        self.assertEqual(cuerpo, [])
        self.assertEqual(len(sesion.llamadas), 2)
        dormir.assert_called()

    def test_reintenta_error_de_red_y_devuelve_si_persiste(self):
        sesion = FakeSesion([
            wp_api.requests.ConnectionError("boom"),
            wp_api.requests.ConnectionError("boom"),
            wp_api.requests.ConnectionError("boom"),
        ])
        cli = self._cliente(sesion)
        cli.api_base = "https://ejemplo.com/wp-json"
        with mock.patch("wp_api.time.sleep"):
            with self.assertRaises(wp_api.requests.ConnectionError):
                cli.get_json("https://ejemplo.com/wp-json/wp/v2/posts")
        self.assertEqual(len(sesion.llamadas), 3)  # 1 intento + 2 reintentos

    def test_retry_after_largo_no_espera(self):
        sesion = FakeSesion([FakeRespuesta(429, {"retry-after": "600"})])
        cli = self._cliente(sesion)
        resp = cli._get_con_reintentos("https://ejemplo.com/wp-json/wp/v2/posts")
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(len(sesion.llamadas), 1)

    def test_robots_permite_uploads(self):
        sesion = FakeSesion([FakeRespuesta(200, {"content-type": "text/plain"},
                                           texto="User-agent: *\nDisallow:\n")])
        cli = self._cliente(sesion)
        info = cli.robots()
        self.assertTrue(info["permite_uploads"])
        self.assertTrue(info["permite_rest"])

    def test_robots_bloquea_uploads(self):
        sesion = FakeSesion([FakeRespuesta(200, {"content-type": "text/plain"},
                                           texto="User-agent: *\nDisallow: /wp-content/uploads/\n")])
        cli = self._cliente(sesion)
        info = cli.robots()
        self.assertFalse(info["permite_uploads"])

    def test_robots_usa_raiz_del_origen(self):
        sesion = FakeSesion([FakeRespuesta(200, {"content-type": "text/plain"},
                                           texto="User-agent: *\nDisallow:\n",
                                           url="https://ejemplo.com/robots.txt")])
        cli = self._cliente(sesion, site="https://ejemplo.com/blog/post")
        info = cli.robots()
        self.assertTrue(info["permite_uploads"])
        self.assertEqual(sesion.llamadas[0]["url"], "https://ejemplo.com/robots.txt")

    def test_descubrir_link_rest_route_y_reusar_base(self):
        sesion = FakeSesion([
            FakeRespuesta(200, {"content-type": "text/html",
                                "link": '<https://ejemplo.com/blog/?rest_route=/>; rel="https://api.w.org/"'},
                          texto="<html></html>", url="https://ejemplo.com/blog/post"),
            FakeRespuesta(200, {"content-type": "application/json", "x-wp-total": "1", "x-wp-totalpages": "1"},
                          {"name": "Sitio", "description": "Desc", "namespaces": ["wp/v2"],
                           "routes": {"/wp/v2/media": {}, "/wp/v2/posts": {}, "/wp/v2/pages": {}}}),
            FakeRespuesta(200, {"x-wp-totalpages": "1", "x-wp-total": "1"}, [
                {"id": 1, "date": "2024-10-01T00:00:00", "slug": "a",
                 "title": {"rendered": "a"}, "source_url": "https://ejemplo.com/blog/wp-content/uploads/2024/10/a.pdf",
                 "mime_type": "application/pdf", "media_details": {"filesize": 10}}
            ]),
        ])
        cli = self._cliente(sesion, site="https://ejemplo.com/blog/post")
        info = cli.discover()
        self.assertTrue(info["ok"])
        self.assertEqual(info["api_base"], "https://ejemplo.com/blog/?rest_route=")
        self.assertEqual(info["fuente"], "link")
        regs = list(cli.listar_media(max_items=1))
        self.assertEqual(regs[0]["url_api"], "https://ejemplo.com/blog/?rest_route=/wp/v2/media/1")
        self.assertEqual(sesion.llamadas[2]["params"]["per_page"], 1)

    def test_descubrir_red_no_se_confunde_con_ausencia(self):
        sesion = FakeSesion([wp_api.requests.ConnectionError("boom")])
        cli = self._cliente(sesion, site="https://ejemplo.com/blog/post")
        info = cli.discover()
        self.assertFalse(info["ok"])
        self.assertEqual(info["error"], "red")
        self.assertEqual(len(sesion.llamadas), 1)

    def test_descubrir_401_no_se_confunde_con_ausencia(self):
        sesion = FakeSesion([FakeRespuesta(401, {"content-type": "application/json"},
                                           texto='{"code":"rest_not_logged_in"}',
                                           url="https://ejemplo.com/blog/post")])
        cli = self._cliente(sesion, site="https://ejemplo.com/blog/post")
        info = cli.discover()
        self.assertFalse(info["ok"])
        self.assertEqual(info["error"], "http_401")
        self.assertEqual(len(sesion.llamadas), 1)

    def test_descargar_rechaza_userinfo_en_url_media(self):
        sesion = FakeSesion([])
        cli = self._cliente(sesion)
        with tempfile.TemporaryDirectory() as td:
            res = cli.descargar_media({"sitio": "https://ejemplo.com", "id": 9, "titulo": "T", "slug": "t",
                                       "url_media": "https://user:pass@ejemplo.com/x.pdf"}, Path(td))
        self.assertEqual(res["estado"], "error_url")
        self.assertEqual(sesion.llamadas, [])

    def test_descargar_rechaza_redireccion_cruzada(self):
        sesion = FakeSesion([FakeRespuesta(302, {"location": "https://evil.test/x.pdf"}, texto="")])
        cli = self._cliente(sesion)
        with tempfile.TemporaryDirectory() as td:
            res = cli.descargar_media({"sitio": "https://ejemplo.com", "id": 10, "titulo": "T", "slug": "t",
                                       "mime_type": "application/pdf",
                                       "url_media": "https://ejemplo.com/x.pdf"}, Path(td))
        self.assertEqual(res["estado"], "error_http")
        self.assertEqual(len(sesion.llamadas), 1)

    def test_descargar_sigue_redireccion_misma_raiz(self):
        sesion = FakeSesion([
            FakeRespuesta(302, {"location": "https://ejemplo.com/wp-content/uploads/2024/10/x.pdf"}, texto=""),
            FakeRespuesta(200, {"content-type": "application/pdf"}, bloques=[pdf_bytes()]),
        ])
        cli = self._cliente(sesion)
        with tempfile.TemporaryDirectory() as td:
            res = cli.descargar_media({"sitio": "https://ejemplo.com", "id": 11, "titulo": "T", "slug": "t",
                                       "mime_type": "application/pdf",
                                       "url_media": "https://ejemplo.com/wp-content/uploads/2024/10/x.pdf"}, Path(td))
        self.assertEqual(res["estado"], "descargado")
        self.assertEqual(len(sesion.llamadas), 2)


class TestDescargaComoComando(unittest.TestCase):
    """Regresion: la segunda corrida debe reutilizar, no volver a descargar.
    Evita el bug de comparar id entero (API) contra id texto (manifest CSV)."""

    def test_segunda_corrida_reutiliza_sin_rebajar(self):
        listado = FakeRespuesta(200, {"x-wp-totalpages": "1"}, [{
            "id": 43887, "date": "2026-07-13T12:39:16", "slug": "catalogo",
            "title": {"rendered": "Catálogo"}, "mime_type": "application/pdf",
            "source_url": "https://www.ejemplo.com/wp-content/uploads/2024/10/a.pdf",
        }])
        sesiones = [
            FakeSesion([listado, FakeRespuesta(200, {"content-type": "application/pdf"},
                                               bloques=[pdf_bytes()])]),
            FakeSesion([listado]),  # segunda corrida: solo el listado
        ]
        original = wp_api.ClienteWP
        creadas = []

        def fabrica(site, pausa=0.0, **kw):
            sesion = sesiones[len(creadas)] if len(creadas) < len(sesiones) else FakeSesion([])
            creadas.append(sesion)
            cli = original(site=site, pausa=0.0, session=sesion)
            cli.api_base = "https://ejemplo.com/wp-json"
            return cli

        with tempfile.TemporaryDirectory() as td:
            args = argparse.Namespace(site="https://ejemplo.com", search="catalogo", url=None,
                                      id=None, mime=None, per_page=100, max=1, sleep=0.0, out=td,
                                      umbral=5, confirmo_bajar=None)
            wp_api.ClienteWP = fabrica
            try:
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(wp_api.cmd_download(args), 0)
                    primera = wp_api.leer_manifest(Path(td) / "manifest.csv")
                    self.assertEqual(primera[0]["estado"], "descargado")
                    self.assertEqual(primera[0]["bytes"], str(len(pdf_bytes())))

                    self.assertEqual(wp_api.cmd_download(args), 0)
                    segunda = wp_api.leer_manifest(Path(td) / "manifest.csv")
            finally:
                wp_api.ClienteWP = original

            self.assertEqual(len(segunda), 1)
            self.assertEqual(segunda[0]["estado"], "reutilizado")
            self.assertEqual(segunda[0]["sha256"], primera[0]["sha256"])
            # La segunda sesion no debe haber pedido el archivo: 1 sola llamada (listado).
            self.assertEqual(len(sesiones[1].llamadas), 1)


class TestExport(unittest.TestCase):
    def _args(self, **kw):
        base = dict(site="https://ejemplo.com", recurso="posts", id=None, search=None,
                    filtro=None, campos=None, formato="json", per_page=100, max=5,
                    sleep=0.0, out=None, umbral=5, confirmo_bajar=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def _parchear(self, respuestas):
        sesion = FakeSesion(respuestas)
        original = wp_api.ClienteWP

        def fabrica(site, pausa=0.0, **kw):
            cli = original(site=site, pausa=0.0, session=sesion)
            cli.api_base = "https://ejemplo.com/wp-json"
            return cli

        wp_api.ClienteWP = fabrica
        return original, sesion

    def test_resolver_recurso(self):
        self.assertEqual(wp_api._resolver_recurso("posts"), "wp/v2/posts")
        self.assertEqual(wp_api._resolver_recurso("wc/v3/products"), "wc/v3/products")
        with self.assertRaises(ValueError):
            wp_api._resolver_recurso("")
        with self.assertRaises(ValueError):
            wp_api._resolver_recurso("../etc/passwd")

    def test_export_json_con_envoltura(self):
        entradas = [{"id": 1, "title": {"rendered": "Uno"}}, {"id": 2, "title": {"rendered": "Dos"}}]
        original, sesion = self._parchear([
            FakeRespuesta(200, {"x-wp-total": "2", "x-wp-totalpages": "1"}, entradas),
        ])
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(wp_api.cmd_export(self._args(out=td)), 0)
                destino = Path(td) / "json" / "wp-v2-posts.json"
                self.assertTrue(destino.is_file())
                envoltura = json.loads(destino.read_text(encoding="utf-8"))
                self.assertEqual(envoltura["recurso"], "wp/v2/posts")
                self.assertEqual(envoltura["total_disponible"], 2)
                self.assertEqual([i["id"] for i in envoltura["items"]], [1, 2])
                filas = wp_api.leer_manifest(Path(td) / "manifest.csv")
                self.assertEqual(filas[0]["estado"], "exportado")
                self.assertEqual(filas[0]["id"], "export:wp/v2/posts")
                self.assertEqual(filas[0]["archivo"], str(destino))
                self.assertEqual(sesion.llamadas[0]["url"],
                                 "https://ejemplo.com/wp-json/wp/v2/posts")
        finally:
            wp_api.ClienteWP = original

    def test_export_ndjson_y_filtros(self):
        entradas = [{"id": 1}, {"id": 2}]
        original, sesion = self._parchear([
            FakeRespuesta(200, {"x-wp-total": "2", "x-wp-totalpages": "1"}, entradas),
        ])
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                args = self._args(out=td, formato="ndjson", filtro=["after=2024-01-01"], campos="id,title")
                self.assertEqual(wp_api.cmd_export(args), 0)
                destino = Path(td) / "json"
                archivo = list(destino.glob("wp-v2-posts-*.ndjson"))
                self.assertEqual(len(archivo), 1)
                lineas = archivo[0].read_text(encoding="utf-8").splitlines()
                self.assertEqual(json.loads(lineas[0]), {"id": 1})
                self.assertEqual(sesion.llamadas[0]["params"]["after"], "2024-01-01")
                self.assertEqual(sesion.llamadas[0]["params"]["_fields"], "id,title")
        finally:
            wp_api.ClienteWP = original

    def test_export_por_id(self):
        original, sesion = self._parchear([
            FakeRespuesta(200, cuerpo={"id": 17, "slug": "entrada"}),
        ])
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(wp_api.cmd_export(self._args(out=td, id="17")), 0)
                self.assertTrue((Path(td) / "json" / "wp-v2-posts-17.json").is_file())
                self.assertTrue(sesion.llamadas[0]["url"].endswith("/wp/v2/posts/17"))
        finally:
            wp_api.ClienteWP = original

    def test_export_filtro_malformado_falla_antes_de_pedir(self):
        original, sesion = self._parchear([])
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    wp_api.cmd_export(self._args(out=td, filtro=["sin-igual"]))
        finally:
            wp_api.ClienteWP = original
        self.assertEqual(sesion.llamadas, [])

    def test_export_frena_por_solicitudes_estimadas(self):
        # max=1000, per_page=100 -> 11 solicitudes estimadas > umbral 5
        original, sesion = self._parchear([])
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                args = self._args(out=td, max=1000)
                self.assertEqual(wp_api.cmd_export(args), 3)
                # Confirmado con el numero de solicitudes exacto: ahora consulta
                args = self._args(out=td, max=1000, confirmo_bajar=10)
                sesion.respuestas.append(FakeRespuesta(200, {"x-wp-total": "0", "x-wp-totalpages": "1"}, []))
                self.assertEqual(wp_api.cmd_export(args), 0)
        finally:
            wp_api.ClienteWP = original
        # El freno ocurre antes de tocar la red
        self.assertEqual(len(sesion.llamadas), 1)

    def test_nombre_export_estable_y_distinto_por_filtros(self):
        base = wp_api._nombre_export("wp/v2/posts", {}, None, None, "json")
        con_filtro = wp_api._nombre_export("wp/v2/posts", {"after": "2024-01-01"}, None, None, "json")
        self.assertEqual(base[0], "export:wp/v2/posts")
        self.assertEqual(base[1], "wp-v2-posts.json")
        self.assertNotEqual(base[1], con_filtro[1])
        self.assertIn("#", con_filtro[0])


class TestVerificacion(unittest.TestCase):
    def _fila(self, td, nombre, contenido, estado="descargado", mime="application/pdf", **extra):
        archivo = Path(td) / nombre
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(contenido)
        fila = wp_api.fila_manifest({"sitio": "https://ejemplo.com", "id": extra.pop("id", "1"),
                                     "mime_type": mime, "url_media": ""},
                                    archivo=str(archivo), estado=estado,
                                    sha256=wp_api.sha256_archivo(archivo), **extra)
        return fila

    def test_verifica_formatos_mixtos_y_legados(self):
        with tempfile.TemporaryDirectory() as td:
            filas = [
                self._fila(td, "documentos/a.pdf", pdf_bytes(), estado="descargado"),
                self._fila(td, "imagenes/b.png", b"\x89PNG\r\n\x1a\n", estado="descargado", mime="image/png", id="2"),
                self._fila(td, "json/wp-v2-posts.json", b'{"items": []}', estado="exportado",
                           mime="application/json", id="3"),
                self._fila(td, "json/wp-v2-tags.ndjson", b'{"id":1}\n{"id":2}\n', estado="exportado",
                           mime="application/json", id="4"),
                # Manifiesto historico con estado antiguo: sigue verificando
                self._fila(td, "documentos/viejo.pdf", pdf_bytes(b"%PDF-1.4 viejo\n"), estado="descargado_pdf",
                           id="5"),
            ]
            manifiesto = Path(td) / "manifest.csv"
            wp_api.escribir_manifest(filas, manifiesto)
            args = argparse.Namespace(out=td)
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                self.assertEqual(wp_api.cmd_verify(args), 0)
            detalle = json.loads(salida.getvalue())
            self.assertEqual(detalle["validas"], 5)

    def test_detecta_json_corrupto_y_hash_alterado(self):
        with tempfile.TemporaryDirectory() as td:
            json_ok = self._fila(td, "json/ok.json", b'{"a": 1}', estado="exportado",
                                 mime="application/json", id="1")
            roto = self._fila(td, "json/roto.json", b'{"a": ', estado="exportado",
                              mime="application/json", id="2")
            alterado = self._fila(td, "documentos/x.pdf", pdf_bytes(), estado="descargado", id="3")
            alterado["sha256"] = "0" * 64
            manifiesto = Path(td) / "manifest.csv"
            wp_api.escribir_manifest([json_ok, roto, alterado], manifiesto)
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                self.assertEqual(wp_api.cmd_verify(argparse.Namespace(out=td)), 1)
            detalle = json.loads(salida.getvalue())
            motivos = {v["id"]: v["motivo"] for v in detalle["detalle"]}
            self.assertEqual(motivos["2"], "json_invalido")
            self.assertEqual(motivos["3"], "hash_mismatch")

    def test_fila_sin_archivo_no_valida(self):
        fila = wp_api.fila_manifest({"sitio": "s", "id": "9", "mime_type": ""},
                                    archivo="", estado="descargado")
        self.assertEqual(wp_api._verificar_fila(fila), (False, "archivo_ausente"))


class TestFrenoDeVolumen(unittest.TestCase):
    """El freno obliga a repetir el numero exacto del preflight."""

    def test_umbral(self):
        f = wp_api.requiere_confirmacion
        self.assertFalse(f(1, 5))
        self.assertFalse(f(5, 5))            # en el umbral no frena
        self.assertTrue(f(6, 5))             # por encima, si
        self.assertFalse(f(6, 5, 6))         # confirmado con el numero exacto
        self.assertTrue(f(6, 5, 7))          # numero equivocado
        self.assertTrue(f(6, 5, "6x"))       # basura
        self.assertTrue(f(2, 0, None))       # umbral 0: todo exige confirmacion

    def test_resumen_preflight(self):
        cliente = types.SimpleNamespace(site="https://ejemplo.com", total_disponible=5443)
        registros = [
            {"id": 1, "titulo": "uno", "bytes_api": 100},
            {"id": 2, "titulo": "dos", "bytes_api": None},
            {"id": 3, "titulo": "tres", "bytes_api": 300},
        ]
        r = wp_api.resumen_preflight(cliente, registros, consulta="catalogo")
        self.assertEqual(r["total_disponible"], 5443)
        self.assertEqual(r["a_descargar"], 3)
        self.assertEqual(r["bytes_conocidos"], 400)
        self.assertEqual(r["sin_tamano"], 1)
        self.assertEqual(r["consulta"], "catalogo")
        self.assertEqual(len(r["muestra"]), 3)

    def _args(self, **kw):
        base = dict(site="https://ejemplo.com", search="catalogo", url=None, id=None, mime=None,
                    per_page=100, max=2, sleep=0.0, umbral=1, confirmo_bajar=None)
        base.update(kw)
        return argparse.Namespace(**base)

    def _sesion_listado(self, n=2):
        items = [{"id": i, "title": {"rendered": f"t{i}"}, "slug": f"t{i}",
                  "mime_type": "application/pdf",
                  "source_url": f"https://www.ejemplo.com/wp-content/uploads/2024/10/{i}.pdf"}
                 for i in range(1, n + 1)]
        return FakeRespuesta(200, {"x-wp-totalpages": "1", "x-wp-total": str(n)}, items)

    def _parchear(self, sesion):
        original = wp_api.ClienteWP

        def fabrica(site, pausa=0.0, **kw):
            cli = original(site=site, pausa=0.0, session=sesion)
            cli.api_base = "https://ejemplo.com/wp-json"
            return cli

        wp_api.ClienteWP = fabrica
        return original

    def test_frena_y_no_descarga(self):
        # Solo hay respuesta de listado: si intentara bajar, la sesion falsa revienta.
        sesion = FakeSesion([self._sesion_listado(2)])
        original = self._parchear(sesion)
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                codigo = wp_api.cmd_download(self._args(out=td))
        finally:
            wp_api.ClienteWP = original
        self.assertEqual(codigo, 3)
        self.assertEqual(len(sesion.llamadas), 1)  # solo el listado

    def test_confirma_y_descarga(self):
        sesion = FakeSesion([self._sesion_listado(2),
                             FakeRespuesta(200, {"content-type": "application/pdf"}, bloques=[pdf_bytes(b"%PDF-1.4\na\n")]),
                             FakeRespuesta(200, {"content-type": "application/pdf"}, bloques=[pdf_bytes(b"%PDF-1.4\nbb\n")])])
        original = self._parchear(sesion)
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                codigo = wp_api.cmd_download(self._args(out=td, confirmo_bajar=2))
                filas = wp_api.leer_manifest(Path(td) / "manifest.csv")
        finally:
            wp_api.ClienteWP = original
        self.assertEqual(codigo, 0)
        self.assertEqual(len(filas), 2)
        self.assertTrue(all(f["estado"] == "descargado" for f in filas))

    def test_descarga_con_error_devuelve_codigo_1(self):
        sesion = FakeSesion([self._sesion_listado(1),
                             FakeRespuesta(404, {"content-type": "text/html"})])
        original = self._parchear(sesion)
        try:
            with tempfile.TemporaryDirectory() as td, \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                codigo = wp_api.cmd_download(self._args(out=td, max=1, umbral=5))
        finally:
            wp_api.ClienteWP = original
        self.assertEqual(codigo, 1)

    def test_preflight_no_descarga(self):
        sesion = FakeSesion([self._sesion_listado(2)])
        original = self._parchear(sesion)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                codigo = wp_api.cmd_preflight(argparse.Namespace(
                    site="https://ejemplo.com", search="catalogo", mime=None, per_page=100, max=2, umbral=5))
        finally:
            wp_api.ClienteWP = original
        self.assertEqual(codigo, 0)
        self.assertEqual(len(sesion.llamadas), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
