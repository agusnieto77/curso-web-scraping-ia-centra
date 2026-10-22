"""Pruebas del cliente de YouTube sin red: funciones puras y cliente con sesion falsa.

Ejecutar:  python youtube-api/validation/test_yt_datos.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))

import yt_datos as Y  # noqa: E402

VIDEO_ID = "j3ZIM9UaXlE"

TIMEDTEXT_V3 = """<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3">
<head><ws id="0"/></head>
<body>
<p t="0" d="4841"><s ac="0">Hola</s><s t="321" ac="0"> mundo</s></p>
<p t="5000" d="2000"><s ac="0">Segundo</s></p>
</body>
</timedtext>"""

TIMEDTEXT_V1 = """<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="1">
<body>
<text start="0" dur="2000">Hola mundo</text>
<text start="2500" dur="1500">Segundo</text>
</body>
</timedtext>"""


class TestExtraerIdVideo(unittest.TestCase):
    def test_desde_url_watch(self):
        self.assertEqual(
            Y.extraer_id_video(f"https://www.youtube.com/watch?v={VIDEO_ID}"), VIDEO_ID
        )

    def test_desde_url_watch_con_parametros(self):
        url = f"https://www.youtube.com/watch?v={VIDEO_ID}&t=42s&list=PL123"
        self.assertEqual(Y.extraer_id_video(url), VIDEO_ID)

    def test_desde_url_short(self):
        self.assertEqual(Y.extraer_id_video(f"https://youtu.be/{VIDEO_ID}"), VIDEO_ID)

    def test_desde_url_shorts(self):
        self.assertEqual(Y.extraer_id_video(f"https://www.youtube.com/shorts/{VIDEO_ID}"), VIDEO_ID)

    def test_id_suelto(self):
        self.assertEqual(Y.extraer_id_video(VIDEO_ID), VIDEO_ID)

    def test_url_invalida(self):
        with self.assertRaises(Y.YouTubeError):
            Y.extraer_id_video("https://www.youtube.com/feed/trending")


class TestSegmentos(unittest.TestCase):
    def test_formato_3(self):
        segmentos = Y.segmentos_desde_timedtext(TIMEDTEXT_V3)
        self.assertEqual(len(segmentos), 2)
        self.assertAlmostEqual(segmentos[0]["inicio"], 0.0)
        self.assertAlmostEqual(segmentos[0]["duracion"], 4.841)
        self.assertEqual(segmentos[0]["texto"], "Hola mundo")
        self.assertAlmostEqual(segmentos[1]["inicio"], 5.0)

    def test_formato_1(self):
        segmentos = Y.segmentos_desde_timedtext(TIMEDTEXT_V1)
        self.assertEqual(len(segmentos), 2)
        self.assertAlmostEqual(segmentos[0]["inicio"], 0.0)
        self.assertEqual(segmentos[1]["texto"], "Segundo")

    def test_xml_corrupto(self):
        with self.assertRaises(Y.YouTubeError):
            Y.segmentos_desde_timedtext("<timedtext><p t='0'>sin cerrar")

    def test_xml_vacio_no_devuelve_segmentos(self):
        self.assertEqual(Y.segmentos_desde_timedtext("<timedtext format='3'></timedtext>"), [])


class TestComentarios(unittest.TestCase):
    def test_entidad_se_localiza_por_prefijo(self):
        entities = {"clave-corta": {"commentEntityPayload": {"properties": {"commentId": "x"}}}}
        self.assertIsNotNone(Y._coincidir_entidad(entities, "clave-corta-sufijo-largo"))
        self.assertIsNone(Y._coincidir_entidad(entities, "otra-clave"))

    def test_view_model_de_hilo_y_de_item(self):
        hilo = {"commentThreadRenderer": {"commentViewModel": {"commentViewModel": {"commentKey": "k1"}}}}
        item = {"commentViewModel": {"commentKey": "k2"}}
        self.assertEqual(Y._view_model(hilo)["commentKey"], "k1")
        self.assertEqual(Y._view_model(item)["commentKey"], "k2")
        self.assertIsNone(Y._view_model({"otro": 1}))

    def test_conteo_de_comentarios_desde_runs(self):
        cabecera = {"commentsCount": {"runs": [{"text": "229"}]}}
        self.assertEqual(Y._contar_comentarios(cabecera), 229)

    def test_conteo_de_comentarios_desde_texto(self):
        cabecera = {"countText": {"runs": [{"text": "1.234"}, {"text": " comentarios"}]}}
        self.assertEqual(Y._contar_comentarios(cabecera), 1234)

    def test_conteo_ausente(self):
        self.assertIsNone(Y._contar_comentarios({}))

    def test_conteo_prefiere_total_exacto_sobre_abreviado(self):
        cabecera = {
            "commentsCount": {"runs": [{"text": "2,4 M"}]},
            "countText": {"runs": [{"text": "2.460.280"}, {"text": " comentarios"}]},
        }
        self.assertEqual(Y._contar_comentarios(cabecera), 2460280)

    def test_conteo_abreviado_sin_total_exacto(self):
        for texto, esperado in (("2,4 M", 2_400_000), ("15 mil", 15_000), ("3.1K", 3_100), ("1,2 mill.", 1_200_000)):
            with self.subTest(texto=texto):
                self.assertEqual(Y._contar_comentarios({"commentsCount": {"simpleText": texto}}), esperado)

    def test_token_de_orden_por_indice(self):
        cabecera = {
            "sortMenu": {
                "sortFilterSubMenuRenderer": {
                    "subMenuItems": [
                        {"title": "Destacados", "serviceEndpoint": {"continuationCommand": {"token": "t-top"}}},
                        {"title": "Mas recientes", "serviceEndpoint": {"continuationCommand": {"token": "t-new"}}},
                    ]
                }
            }
        }
        self.assertEqual(Y._token_de_orden(cabecera, "top")["continuation"], "t-top")
        self.assertEqual(Y._token_de_orden(cabecera, "newest")["continuation"], "t-new")
        self.assertIsNone(Y._token_de_orden({}, "top"))

    def test_siguiente_consulta_desde_endpoint_directo(self):
        items = [
            {
                "continuationItemRenderer": {
                    "continuationEndpoint": {
                        "clickTrackingParams": "ctp",
                        "continuationCommand": {"token": "siguiente"},
                    }
                }
            }
        ]
        consulta = Y._siguiente_consulta(items)
        self.assertEqual(consulta["continuation"], "siguiente")
        self.assertEqual(consulta["clickTracking"]["clickTrackingParams"], "ctp")

    def test_siguiente_consulta_desde_boton_de_respuestas(self):
        items = [
            {
                "continuationItemRenderer": {
                    "button": {
                        "buttonRenderer": {
                            "command": {
                                "clickTrackingParams": "ctp2",
                                "continuationCommand": {"token": "mas-respuestas"},
                            }
                        }
                    }
                }
            }
        ]
        self.assertEqual(Y._siguiente_consulta(items)["continuation"], "mas-respuestas")

    def test_sin_continuacion_devuelve_none(self):
        self.assertIsNone(Y._siguiente_consulta([{"commentThreadRenderer": {}}]))


class TestPistasSubtitulo(unittest.TestCase):
    def test_prefiere_subtitulo_manual(self):
        lista = [
            {"languageCode": "es", "kind": "asr"},
            {"languageCode": "es", "kind": None},
        ]
        self.assertEqual(Y._elegir_pista(lista)["kind"], None)

    def test_prefiere_el_idioma_del_cliente_entre_automaticas(self):
        lista = [
            {"languageCode": "ar", "kind": "asr"},
            {"languageCode": "es", "kind": "asr"},
            {"languageCode": "en", "kind": "asr"},
        ]
        self.assertEqual(Y._elegir_pista(lista)["languageCode"], "es")

    def test_primera_pista_si_no_hay_preferencia(self):
        lista = [{"languageCode": "ar", "kind": "asr"}]
        self.assertEqual(Y._elegir_pista(lista)["languageCode"], "ar")


class TestMetadatos(unittest.TestCase):
    def test_normalizacion_desde_player(self):
        player = {
            "videoDetails": {
                "videoId": VIDEO_ID,
                "title": "Titulo",
                "author": "Canal",
                "channelId": "UC1",
                "viewCount": "100",
                "lengthSeconds": "604",
                "shortDescription": "Descripcion",
                "keywords": ["a", "b"],
            },
            "microformat": {
                "playerMicroformatRenderer": {
                    "category": "Tech",
                    "likeCount": "12",
                    "publishDate": "2026-10-21T07:02:25-07:00",
                }
            },
            "playabilityStatus": {"status": "OK"},
        }
        datos = Y.metadatos_desde_player(player)
        self.assertEqual(datos["titulo"], "Titulo")
        self.assertEqual(datos["vistas"], 100)
        self.assertEqual(datos["likes"], 12)
        self.assertEqual(datos["duracion_s"], 604)
        self.assertEqual(datos["categoria"], "Tech")
        self.assertEqual(datos["keywords"], ["a", "b"])
        self.assertFalse(datos["es_en_vivo"])
        self.assertEqual(datos["disponibilidad"], "OK")


class TestJsonEmpotrado(unittest.TestCase):
    def test_no_corta_en_llave_y_punto_y_coma_dentro_de_un_string(self):
        html = (
            '<script>var ytInitialPlayerResponse = {"videoDetails": {"title": "a};b", '
            '"videoId": "x"}};var otra = 1;</script>'
        )
        datos = Y.extraer_respuesta_player(html)
        self.assertEqual(datos["videoDetails"]["title"], "a};b")

    def test_asignacion_por_corchetes(self):
        html = '<script>window["ytInitialData"] = {"a": 1};</script>'
        self.assertEqual(Y.extraer_datos_iniciales(html), {"a": 1})

    def test_ausente_devuelve_none(self):
        self.assertIsNone(Y.extraer_respuesta_player("<html>sin datos</html>"))


class FakeRespuesta:
    def __init__(self, status=200, texto="", cuerpo=None, headers=None):
        self.status_code = status
        self.text = texto
        self.content = texto.encode("utf-8")
        self._cuerpo = cuerpo
        self.headers = headers or {}

    def json(self):
        return self._cuerpo


class FakeSesion:
    def __init__(self, gets=None, posts=None):
        self.headers = {}
        self.gets = list(gets or [])
        self.posts = list(posts or [])
        self.llamadas = []

    def get(self, url, timeout=None, **kwargs):
        self.llamadas.append(("GET", url))
        return self.gets.pop(0)

    def post(self, url, json=None, timeout=None):
        self.llamadas.append(("POST", url))
        return self.posts.pop(0)


class TestCliente(unittest.TestCase):
    def test_retry_after_con_fecha_http_no_rompe(self):
        respuesta = FakeRespuesta(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        self.assertEqual(Y.ClienteYouTube._espera_429(respuesta), 10.0)
        self.assertEqual(Y.ClienteYouTube._espera_429(FakeRespuesta(429, headers={"Retry-After": "600"})), 30.0)

    def test_ficha_y_reproductor_se_piden_una_vez_por_video(self):
        html = (
            '"INNERTUBE_API_KEY":"clave123"'
            'var ytInitialPlayerResponse = {"videoDetails": {"videoId": "%s", "title": "T"}, '
            '"playabilityStatus": {"status": "OK"}};' % VIDEO_ID
        )
        player = {
            "playabilityStatus": {"status": "OK"},
            "captions": {"playerCaptionsTracklistRenderer": {"captionTracks": [
                {"languageCode": "es", "kind": "asr", "baseUrl": "https://www.youtube.com/api/timedtext?x=1"}
            ]}},
        }
        sesion = FakeSesion(
            gets=[FakeRespuesta(200, html), FakeRespuesta(200, TIMEDTEXT_V3), FakeRespuesta(200, TIMEDTEXT_V3)],
            posts=[FakeRespuesta(200, cuerpo=player)],
        )
        cliente = Y.ClienteYouTube(sesion=sesion, pausar=0)
        self.assertEqual(cliente.metadatos(VIDEO_ID)["titulo"], "T")
        self.assertEqual(len(cliente.transcripcion(VIDEO_ID)["segmentos"]), 2)
        self.assertEqual(len(cliente.pistas_subtitulo(VIDEO_ID)), 1)
        self.assertEqual(len(cliente.transcripcion(VIDEO_ID, "es")["segmentos"]), 2)
        fichas = [u for m, u in sesion.llamadas if m == "GET" and "/watch?" in u]
        reproductor = [u for m, u in sesion.llamadas if m == "POST" and "/player" in u]
        self.assertEqual(len(fichas), 1)
        self.assertEqual(len(reproductor), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
