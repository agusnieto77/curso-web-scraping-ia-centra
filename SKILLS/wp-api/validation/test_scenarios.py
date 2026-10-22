"""Escenarios reproducibles para validar la matriz y un smoke HTTP local.

Cubre: descubrimiento con rutas bonitas y rest_route, subdirectorio, errores
401/403/404/red, listado multi-formato, descarga end-to-end de PDF/PNG/JSON,
archivo trampa (HTML con 200) y exportacion JSON de colecciones.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

import wp_api  # noqa: E402


CLI = Path(__file__).resolve().parents[1] / "assets" / "wp_api.py"

PDF_DEMO = b"%PDF-1.4\n% Escenario local de validacion\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n"
PNG_DEMO = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x00" * 20
JSON_DEMO = b'{"demo": true, "items": [1, 2]}'
TRAMPA_HTML = b"<html><body>pagina de error disfrazada</body></html>"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class EscenarioHandler(http.server.BaseHTTPRequestHandler):
    server_version = "EscenarioHTTP/1.0"

    def log_message(self, format, *args):  # pragma: no cover - ruido de servidor
        return

    def _send(self, status: int, content_type: str, body: bytes, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict | list, headers: dict[str, str] | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body, headers=headers)

    def _text(self, status: int, text: str | bytes, content_type: str = "text/plain; charset=utf-8"):
        cuerpo = text if isinstance(text, bytes) else text.encode("utf-8")
        self._send(status, content_type, cuerpo)

    def _base_url(self) -> str:
        host = self.server.server_address[0]
        port = self.server.server_address[1]
        return f"http://{host}:{port}"

    def _discovery_payload(self, prefix: str = "") -> dict:
        return {
            "name": "Escenario local",
            "description": "Servidor local de validacion",
            "url": self._base_url() + prefix,
            "home": self._base_url() + prefix,
            "namespaces": ["wp/v2"],
            "routes": {
                "/wp/v2/media": {},
                "/wp/v2/posts": {},
                "/wp/v2/pages": {},
                "/wp/v2/types": {},
            },
        }

    def _media_payload(self, prefix: str = "") -> list[dict]:
        base = self._base_url() + prefix
        return [
            {
                "id": 1,
                "date": "2026-01-01T00:00:00",
                "slug": "demo-pdf",
                "title": {"rendered": "Demo PDF"},
                "mime_type": "application/pdf",
                "source_url": f"{base}/wp-content/uploads/2026/01/demo.pdf",
                "media_details": {"filesize": len(PDF_DEMO)},
            },
            {
                "id": 2,
                "date": "2026-01-02T00:00:00",
                "slug": "logo",
                "title": {"rendered": "Logo PNG"},
                "mime_type": "image/png",
                "source_url": f"{base}/wp-content/uploads/2026/01/logo.png",
                "media_details": {"filesize": len(PNG_DEMO)},
            },
            {
                "id": 3,
                "date": "2026-01-03T00:00:00",
                "slug": "datos",
                "title": {"rendered": "Datos JSON"},
                "mime_type": "application/json",
                "source_url": f"{base}/wp-content/uploads/2026/01/datos.json",
                "media_details": {"filesize": len(JSON_DEMO)},
            },
        ]

    def _posts_payload(self, prefix: str = "") -> list[dict]:
        base = self._base_url() + prefix
        return [
            {"id": 101, "slug": "primera", "title": {"rendered": "Primera entrada"}, "link": f"{base}/primera"},
            {"id": 102, "slug": "segunda", "title": {"rendered": "Segunda entrada"}, "link": f"{base}/segunda"},
        ]

    def _tipos_payload(self) -> dict:
        return {"post": {"name": "Posts", "rest_base": "posts"}, "page": {"name": "Pages", "rest_base": "pages"}}

    def _auth_error(self):
        return self._text(getattr(self.server, "auth_status", 401), "<html>auth</html>", content_type="text/html; charset=utf-8")

    def _sirve_archivos(self, path: str) -> bool:
        if path == "/wp-content/uploads/2026/01/demo.pdf":
            return self._send(200, "application/pdf", PDF_DEMO)
        if path == "/wp-content/uploads/2026/01/logo.png":
            return self._send(200, "image/png", PNG_DEMO)
        if path == "/wp-content/uploads/2026/01/datos.json":
            return self._send(200, "application/json", JSON_DEMO)
        if path == "/wp-content/uploads/2026/01/trampa.pdf":
            # 200 con HTML: un servidor roto no debe convertirse en "PDF"
            return self._send(200, "text/html; charset=utf-8", TRAMPA_HTML)
        return False

    def _media(self, prefix: str = "", query: dict | None = None):
        items = self._media_payload(prefix)
        filtro = (query or {}).get("mime_type")
        if filtro:
            permitidos = {m.strip() for m in filtro[0].split(",") if m.strip()}
            items = [i for i in items if i["mime_type"] in permitidos]
        self._json(200, items, {"X-WP-Total": str(len(items)), "X-WP-TotalPages": "1"})

    def do_GET(self):  # noqa: N802 - contrato de BaseHTTPRequestHandler
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        mode = getattr(self.server, "mode", "root_ok")

        if mode == "subdir_only":
            if parsed.path == "/blog/wp-json/":
                return self._json(200, self._discovery_payload(prefix="/blog"))
            if parsed.path == "/blog/robots.txt":
                return self._text(200, "User-agent: *\nDisallow:\n")
            if parsed.path == "/blog/wp-json/wp/v2/media":
                return self._media(prefix="/blog", query=query)
            if parsed.path.startswith("/blog/wp-content/uploads/"):
                if self._sirve_archivos(parsed.path[len("/blog"):]):
                    return None
            return self._text(404, "<html>404</html>", content_type="text/html; charset=utf-8")

        if mode == "rest_route_only":
            if parsed.path == "/" and query.get("rest_route") == ["/"]:
                return self._json(200, self._discovery_payload())
            if parsed.path == "/robots.txt":
                return self._text(200, "User-agent: *\nDisallow:\n")
            if parsed.path == "/" and query.get("rest_route") == ["/wp/v2/media"]:
                return self._media(query=query)
            if parsed.path == "/" and query.get("rest_route") == ["/wp/v2/posts"]:
                return self._json(200, self._posts_payload(), {"X-WP-Total": "2", "X-WP-TotalPages": "1"})
            return self._text(404, "<html>404</html>", content_type="text/html; charset=utf-8")

        if mode == "root_404":
            if parsed.path == "/robots.txt":
                return self._text(200, "User-agent: *\nDisallow:\n")
            return self._text(404, "<html>404</html>", content_type="text/html; charset=utf-8")

        if mode == "root_401":
            if parsed.path == "/robots.txt":
                return self._text(200, "User-agent: *\nDisallow:\n")
            return self._auth_error()

        if mode == "root_403":
            if parsed.path == "/robots.txt":
                return self._text(200, "User-agent: *\nDisallow:\n")
            self.server.auth_status = 403
            return self._auth_error()

        if parsed.path in {"/wp-json", "/wp-json/"}:
            return self._json(200, self._discovery_payload(), {
                "X-WP-Total": "1",
                "X-WP-TotalPages": "1",
            })
        if parsed.path == "/robots.txt":
            return self._text(200, "User-agent: *\nDisallow:\n")
        if parsed.path == "/wp-json/wp/v2/media":
            return self._media(query=query)
        if parsed.path == "/wp-json/wp/v2/posts":
            return self._json(200, self._posts_payload(), {"X-WP-Total": "2", "X-WP-TotalPages": "1"})
        if parsed.path == "/wp-json/wp/v2/types":
            return self._json(200, self._tipos_payload())
        if parsed.path.startswith("/wp-content/uploads/"):
            if self._sirve_archivos(parsed.path):
                return None
        return self._text(404, "<html>404</html>", content_type="text/html; charset=utf-8")


@contextlib.contextmanager
def escenario_http(mode: str = "root_ok"):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), EscenarioHandler)
    server.mode = mode
    server.auth_status = 401
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class TestHTTPLocal(unittest.TestCase):
    def test_descubrimiento_robots_y_media_en_servidor_local(self):
        with escenario_http("root_ok") as site:
            cli = wp_api.ClienteWP(site=site, pausa=0.0, session=wp_api.requests.Session())

            descubrimiento = cli.discover()
            self.assertEqual(descubrimiento["rutas_clave"]["media"], "/wp/v2/media")
            self.assertIn("wp/v2", descubrimiento["namespaces"])

            robots = cli.robots()
            self.assertTrue(robots["permite_uploads"])

            registros = list(cli.listar_media(mimes=["application/pdf"], max_items=5))
            self.assertEqual(len(registros), 1)
            self.assertEqual(registros[0]["id"], 1)
            self.assertEqual(registros[0]["titulo"], "Demo PDF")
            self.assertTrue(registros[0]["url_media"].endswith("demo.pdf"))

    def test_cli_media_filtra_por_mime_y_por_alias(self):
        with escenario_http("root_ok") as site:
            solo_pdf = _run_cli("media", "--site", site, "--sleep", "0", "--mime", "pdf")
            self.assertEqual(solo_pdf.returncode, 0, solo_pdf.stderr)
            salida = json.loads(solo_pdf.stdout)
            self.assertEqual(salida["total_listado"], 1)
            self.assertEqual(salida["registros"][0]["mime_type"], "application/pdf")

            mezcla = _run_cli("media", "--site", site, "--sleep", "0", "--mime", "pdf,jpg")
            self.assertEqual(json.loads(mezcla.stdout)["total_listado"], 1)

            todos = _run_cli("media", "--site", site, "--sleep", "0")
            self.assertEqual(json.loads(todos.stdout)["total_listado"], 3)

            desconocido = _run_cli("media", "--site", site, "--sleep", "0", "--mime", "docx2")
            self.assertEqual(desconocido.returncode, 2)

    def test_cli_descarga_multiformato_y_verifica(self):
        with escenario_http("root_ok") as site, tempfile.TemporaryDirectory() as td:
            descarga = _run_cli("download", "--site", site, "--sleep", "0",
                                "--max", "3", "--out", td)
            self.assertEqual(descarga.returncode, 0, descarga.stderr)
            filas = wp_api.leer_manifest(Path(td) / "manifest.csv")
            por_id = {f["id"]: f for f in filas}
            self.assertEqual(len(filas), 3)
            self.assertEqual(por_id["1"]["estado"], "descargado")
            self.assertEqual(por_id["2"]["estado"], "descargado")
            self.assertEqual(por_id["3"]["estado"], "descargado")
            # Cada formato cae en su familia
            self.assertTrue(por_id["1"]["archivo"].replace("\\", "/").endswith("/documentos/2026/01/1-demo-pdf.pdf"))
            self.assertTrue(por_id["2"]["archivo"].replace("\\", "/").endswith("/imagenes/2026/01/2-logo.png"))
            self.assertTrue(por_id["3"]["archivo"].replace("\\", "/").endswith("/datos/2026/01/3-datos.json"))
            self.assertEqual(Path(por_id["1"]["archivo"]).read_bytes(), PDF_DEMO)
            self.assertEqual(Path(por_id["2"]["archivo"]).read_bytes(), PNG_DEMO)

            verificacion = _run_cli("verify", "--out", td)
            self.assertEqual(verificacion.returncode, 0, verificacion.stdout)
            self.assertEqual(json.loads(verificacion.stdout)["validas"], 3)

            # Segunda corrida reutiliza sin pedir los bytes de nuevo
            redescarga = _run_cli("download", "--site", site, "--sleep", "0",
                                  "--max", "3", "--out", td)
            self.assertEqual(redescarga.returncode, 0, redescarga.stderr)
            filas2 = wp_api.leer_manifest(Path(td) / "manifest.csv")
            self.assertTrue(all(f["estado"] == "reutilizado" for f in filas2))

    def test_cli_descarga_trampa_html_como_pdf_falla_sin_guardar(self):
        with escenario_http("root_ok") as site, tempfile.TemporaryDirectory() as td:
            proc = _run_cli("download", "--site", site, "--sleep", "0",
                            "--url", f"{site}/wp-content/uploads/2026/01/trampa.pdf",
                            "--out", td)
            self.assertEqual(proc.returncode, 1)
            filas = wp_api.leer_manifest(Path(td) / "manifest.csv")
            self.assertEqual(filas[0]["estado"], "tipo_inesperado")
            self.assertIn("text/html", filas[0]["motivo"])
            self.assertFalse(list(Path(td).rglob("*.pdf")))

    def test_cli_export_posts_y_types_con_verify(self):
        with escenario_http("root_ok") as site, tempfile.TemporaryDirectory() as td:
            export = _run_cli("export", "--site", site, "--sleep", "0",
                              "--recurso", "posts", "--max", "10", "--out", td)
            self.assertEqual(export.returncode, 0, export.stderr)
            detalle = json.loads(export.stdout)
            self.assertEqual(detalle["items"], 2)
            envoltura = json.loads(Path(detalle["archivo"]).read_text(encoding="utf-8"))
            self.assertEqual(envoltura["recurso"], "wp/v2/posts")
            self.assertEqual([i["id"] for i in envoltura["items"]], [101, 102])

            tipos = _run_cli("export", "--site", site, "--sleep", "0",
                             "--recurso", "types", "--out", td)
            self.assertEqual(tipos.returncode, 0, tipos.stderr)
            envoltura_tipos = json.loads(Path(json.loads(tipos.stdout)["archivo"]).read_text(encoding="utf-8"))
            # Coleccion objeto envuelta con su clave
            self.assertEqual({i["__clave"] for i in envoltura_tipos["items"]}, {"post", "page"})

            verificacion = _run_cli("verify", "--out", td)
            self.assertEqual(verificacion.returncode, 0, verificacion.stdout)
            self.assertEqual(json.loads(verificacion.stdout)["validas"], 2)

    def test_cli_export_por_id_y_ndjson(self):
        with escenario_http("root_ok") as site, tempfile.TemporaryDirectory() as td:
            proc = _run_cli("export", "--site", site, "--sleep", "0",
                            "--recurso", "posts", "--id", "101", "--formato", "ndjson",
                            "--out", td)
            # El fixture no sirve /wp-json/wp/v2/posts/101: 404 controlado
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stderr.strip().splitlines()[-1])["error"], "http")

    def test_cli_export_frena_solicitudes_grandes(self):
        with escenario_http("root_ok") as site, tempfile.TemporaryDirectory() as td:
            proc = _run_cli("export", "--site", site, "--sleep", "0",
                            "--recurso", "posts", "--max", "2000", "--out", td)
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(json.loads(proc.stderr.strip().splitlines()[-1])["solicitudes_estimadas"], 20)
            self.assertFalse((Path(td) / "json").exists() and list((Path(td) / "json").iterdir()))

    def test_cli_discover_en_401_y_403(self):
        for mode, status in (("root_401", 401), ("root_403", 403)):
            with self.subTest(mode=mode):
                with escenario_http(mode) as site:
                    proc = _run_cli("discover", "--site", site)
                    self.assertNotEqual(proc.returncode, 0)
                    diagnostico = json.loads(proc.stderr)
                    self.assertEqual(diagnostico["info"]["error"], f"http_{status}")
                    self.assertEqual(diagnostico["info"]["status"], status)

    def test_cli_discover_en_red_caida(self):
        site = f"http://127.0.0.1:{_puerto_libre()}"
        proc = _run_cli("discover", "--site", site)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stderr)["info"]["error"], "red")

    def test_discover_sabe_trabajar_en_subdirectorio(self):
        with escenario_http("subdir_only") as site:
            cli = wp_api.ClienteWP(site=f"{site}/blog", pausa=0.0, session=wp_api.requests.Session())
            descubrimiento = cli.discover()
            self.assertEqual(descubrimiento["rutas_clave"]["media"], "/wp/v2/media")
            self.assertEqual(cli.site, f"{site}/blog")

    def test_enlaces_simples_descubren_y_consultan_media_y_posts(self):
        with escenario_http("rest_route_only") as site:
            cli = wp_api.ClienteWP(site=site, pausa=0.0, session=wp_api.requests.Session())
            cli.discover()
            registros = list(cli.listar_media(mimes=["application/pdf"], max_items=1))
            self.assertEqual(registros[0]["id"], 1)
            self.assertEqual(registros[0]["titulo"], "Demo PDF")
            items, total, _ = cli._iterar_coleccion(
                wp_api.ruta_coleccion_api(cli.api_base, "wp/v2/posts"), {})
            self.assertEqual(len(items), 2)

    def test_cli_discover_emite_json_sin_ciclos(self):
        with escenario_http() as site:
            proc = _run_cli("discover", "--site", site)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            info = json.loads(proc.stdout)["discover"]
            self.assertTrue(info["ok"])
            self.assertEqual(info["rutas_clave"]["media"], "/wp/v2/media")

    def test_discover_en_404_sigue_siendo_error_controlado(self):
        with escenario_http("root_404") as site:
            cli = wp_api.ClienteWP(site=site, pausa=0.0, session=wp_api.requests.Session())
            info = cli.discover()
            self.assertFalse(info["ok"])
            self.assertEqual(info["error"], "ausencia_api")
            self.assertEqual(info["status"], 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
