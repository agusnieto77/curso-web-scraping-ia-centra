#!/usr/bin/env python3
"""Cliente de datos publicos de YouTube: metadatos, transcripcion y comentarios.

Uso:
    python yt_datos.py metadatos    --url https://www.youtube.com/watch?v=ID [--out datos]
    python yt_datos.py transcripcion --url https://www.youtube.com/watch?v=ID [--lang es] [--out datos]
    python yt_datos.py comentarios  --url https://www.youtube.com/watch?v=ID [--max 200] [--con-respuestas] [--out datos]
    python yt_datos.py todo         --url https://www.youtube.com/watch?v=ID [--max 200] [--out datos]

Solo lectura: no envia credenciales ni modifica nada en YouTube. Usa la API
interna (InnerTube) y las paginas publicas de watch, igual que un navegador
anonimo. Si el sitio exige sesion, se informa el bloqueo en lugar de evadirlo.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

try:  # Windows no trae CA del sistema para OpenSSL: usar el almacen del SO.
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - entornos sin truststore
    pass

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TIMEOUT = 30.0
PAUSA = 1.0  # segundos entre peticiones: no martillar el servidor.
CLIENT_ANDROID = {"clientName": "ANDROID", "clientVersion": "20.10.38"}
CLIENT_WEB = {"clientName": "WEB", "clientVersion": "2.20240101.00.00"}


class YouTubeError(RuntimeError):
    """Error recuperable de la recoleccion."""


# --------------------------------------------------------------------------- #
# Utilidades puras (sin red): se pueden probar de forma aislada.
# --------------------------------------------------------------------------- #
def extraer_id_video(url: str) -> str:
    """Devuelve el ID de 11 caracteres de una URL o ID de YouTube."""
    texto = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", texto):
        return texto
    partes = urlparse(texto)
    if partes.netloc.endswith("youtu.be"):
        id_ = partes.path.strip("/").split("/")[0]
    elif "v" in parse_qs(partes.query):
        id_ = parse_qs(partes.query)["v"][0]
    else:
        segmentos = [s for s in partes.path.split("/") if s]
        if len(segmentos) >= 2 and segmentos[0] in {"shorts", "embed", "live", "v"}:
            id_ = segmentos[1]
        else:
            candidatos = re.findall(r"[?&]v=([A-Za-z0-9_-]{11})", texto)
            id_ = candidatos[0] if candidatos else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", id_):
        raise YouTubeError(f"No se pudo deducir el ID del video a partir de {url!r}")
    return id_


def _json_empotrado(html: str, variable: str) -> dict | None:
    """Extrae un objeto JSON asignado a una variable global de la pagina.

    Decodifica desde la llave de apertura con raw_decode: un regex no codicioso
    cortaria en el primer "};" que aparezca dentro de un string del JSON.
    """
    decodificador = json.JSONDecoder()
    for patron in (
        rf"var\s+{variable}\s*=\s*",
        rf'"{variable}"\]\s*=\s*',
        rf"\b{variable}\s*=\s*",
    ):
        for m in re.finditer(patron, html):
            inicio = m.end()
            if not html.startswith("{", inicio):
                continue
            try:
                objeto, _ = decodificador.raw_decode(html, inicio)
            except json.JSONDecodeError:
                continue
            if isinstance(objeto, dict):
                return objeto
    return None


def extraer_respuesta_player(html: str) -> dict | None:
    """ytInitialPlayerResponse: metadatos del video y pistas de subtitulo."""
    return _json_empotrado(html, "ytInitialPlayerResponse")


def extraer_datos_iniciales(html: str) -> dict | None:
    """ytInitialData: seccion de comentarios y demas contenido de la pagina."""
    return _json_empotrado(html, "ytInitialData")


def _texto_runs(runs: list | None) -> str:
    if not isinstance(runs, list):
        return ""
    return "".join(str(r.get("text", "")) for r in runs if isinstance(r, dict))


def metadatos_desde_player(player: dict) -> dict:
    """Normaliza los metadatos utiles de la respuesta del reproductor."""
    detalles = player.get("videoDetails") or {}
    micro = (player.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    estado = (player.get("playabilityStatus") or {}).get("status")
    return {
        "video_id": detalles.get("videoId"),
        "titulo": detalles.get("title"),
        "canal": detalles.get("author"),
        "canal_id": detalles.get("channelId"),
        "vistas": int(detalles.get("viewCount") or 0),
        "duracion_s": int(detalles.get("lengthSeconds") or 0),
        "descripcion": detalles.get("shortDescription") or "",
        "keywords": detalles.get("keywords") or [],
        "categoria": micro.get("category"),
        "likes": int(micro.get("likeCount") or 0),
        "fecha_publicacion": micro.get("publishDate"),
        "fecha_subida": micro.get("uploadDate"),
        "es_en_vivo": bool(detalles.get("isLiveContent")),
        "disponibilidad": estado,
    }


def segmentos_desde_timedtext(xml_texto: str) -> list[dict]:
    """Convierte el XML timedtext (formatos 1 y 3) en segmentos con tiempo."""
    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError as exc:
        raise YouTubeError(f"Respuesta de subtitulos no interpretable: {exc}") from exc
    segmentos: list[dict] = []
    for nodo in raiz.iter():
        if nodo.tag == "text":  # formato 1: <text start dur>texto</text>
            inicio = float(nodo.get("start") or 0)
            dur = float(nodo.get("dur") or 0)
            texto = "".join(nodo.itertext())
            if texto.strip():
                segmentos.append({"inicio": inicio, "duracion": dur, "texto": texto.strip()})
        elif nodo.tag == "p":  # formato 3: <p t d><s>trozo</s></p>
            inicio = float(nodo.get("t") or 0) / 1000.0
            dur = float(nodo.get("d") or 0) / 1000.0
            texto = "".join(nodo.itertext())
            if texto.strip():
                segmentos.append({"inicio": inicio, "duracion": dur, "texto": texto.strip()})
    return segmentos


def _buscar_seccion_comentarios(datos: dict | None) -> dict | None:
    """Localiza el bloque comment-item-section dentro de ytInitialData."""
    if not isinstance(datos, dict):
        return None

    def recorrer(nodo):
        if isinstance(nodo, dict):
            if nodo.get("sectionIdentifier") == "comment-item-section":
                return nodo
            for valor in nodo.values():
                hallazgo = recorrer(valor)
                if hallazgo:
                    return hallazgo
        elif isinstance(nodo, list):
            for valor in nodo:
                hallazgo = recorrer(valor)
                if hallazgo:
                    return hallazgo
        return None

    return recorrer(datos)


def _tokens_continuacion(nodo) -> list[dict]:
    """Tokens de continuacion hallados en cualquier parte de un subarbol."""
    hallados: list[dict] = []
    if isinstance(nodo, dict):
        comando = nodo.get("continuationCommand")
        if isinstance(comando, dict) and comando.get("token"):
            hallados.append(
                {
                    "token": comando["token"],
                    "click_tracking": nodo.get("clickTrackingParams"),
                }
            )
        for valor in nodo.values():
            hallados.extend(_tokens_continuacion(valor))
    elif isinstance(nodo, list):
        for valor in nodo:
            hallados.extend(_tokens_continuacion(valor))
    return hallados


def _view_model(item: dict) -> dict | None:
    """Normaliza el view model de un comentario (nuevo y viejo formato)."""
    vm = item.get("commentViewModel")
    if isinstance(vm, dict):
        return vm.get("commentViewModel", vm)
    hilo = item.get("commentThreadRenderer")
    if isinstance(hilo, dict):
        vm = hilo.get("commentViewModel")
        if isinstance(vm, dict):
            return vm.get("commentViewModel", vm)
    return None


def _coincidir_entidad(entities: dict, clave: str) -> dict | None:
    """Localiza la entidad de un comentario por clave (exacto o prefijo)."""
    if not clave:
        return None
    directa = entities.get(clave)
    if directa:
        return directa
    for entidad, payload in entities.items():
        if clave.startswith(entidad):
            return payload
    return None


def _elegir_pista(lista: list[dict]) -> dict:
    """Pista por defecto: subtitulo manual antes que automatico, y el idioma del cliente."""
    manual = [p for p in lista if p.get("kind") != "asr"]
    candidatas = manual or lista
    for codigo in ("es", "es-419", "en"):
        for pista in candidatas:
            if pista.get("languageCode") == codigo:
                return pista
    return candidatas[0]


def _consulta_continuacion(token: dict) -> dict:
    """Arma el cuerpo de consulta para un token de continuacion."""
    consulta = {"continuation": token["token"]}
    if token.get("click_tracking"):
        consulta["clickTracking"] = {"clickTrackingParams": token["click_tracking"]}
    return consulta


_SUFIJOS_CONTEO = (
    (r"(mil\s*mill|bn|b)\b", 1_000_000_000),
    (r"(mill|m)\b", 1_000_000),
    (r"(mil|k)\b", 1_000),
)


def _numero_de_conteo(texto: str) -> int | None:
    """Convierte "2.460.280", "1,234", "2,4 M", "15 mil" o "3.1K" en entero.

    Las formas abreviadas son aproximadas; por eso se prefiere el texto exacto.
    """
    limpio = str(texto).strip().lower().replace("\xa0", " ")
    for patron, factor in _SUFIJOS_CONTEO:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*" + patron, limpio)
        if m:
            return int(round(float(m.group(1).replace(",", ".")) * factor))
    digitos = re.sub(r"[^\d]", "", limpio)
    return int(digitos) if digitos else None


def _contar_comentarios(cabecera: dict) -> int | None:
    """Total de comentarios declarado por la pagina.

    `countText` trae el total exacto ("2.460.280 comentarios"); `commentsCount`
    suele venir abreviado ("2,4 M"). Se usa el primero cuando existe.
    """
    for clave in ("countText", "commentsCount"):
        bloque = cabecera.get(clave) or {}
        texto = bloque.get("simpleText") or _texto_runs(bloque.get("runs"))
        if texto:
            numero = _numero_de_conteo(texto)
            if numero is not None:
                return numero
    return None


def _token_de_orden(cabecera: dict, orden: str) -> dict | None:
    """Token de clasificacion ("Destacados" / "Mas recientes") de la cabecera."""
    submenu = (
        ((cabecera.get("sortMenu") or {}).get("sortFilterSubMenuRenderer") or {}).get("subMenuItems") or []
    )
    if not submenu:
        return None
    indice = 1 if orden == "newest" else 0
    if indice >= len(submenu):
        return None
    tokens = _tokens_continuacion(submenu[indice])
    return _consulta_continuacion(tokens[0]) if tokens else None


def _siguiente_consulta(items: list) -> dict | None:
    """Consulta de la pagina siguiente, si la pagina la publica.

    Los hilos de respuestas anidan el token en un boton ("Mostrar mas
    respuestas") en lugar del endpoint directo.
    """
    for item in items:
        if not isinstance(item, dict):
            continue
        bloque = item.get("continuationItemRenderer")
        if not isinstance(bloque, dict):
            continue
        candidatos = [
            bloque.get("continuationEndpoint") or {},
            ((bloque.get("button") or {}).get("buttonRenderer") or {}).get("command") or {},
        ]
        for endpoint in candidatos:
            comando = endpoint.get("continuationCommand") or {}
            if comando.get("token"):
                return _consulta_continuacion(
                    {
                        "token": comando["token"],
                        "click_tracking": endpoint.get("clickTrackingParams"),
                    }
                )
    return None


def item_por_id(items: list, comment_id: str | None) -> dict:
    """Localiza el item de hilo que corresponde a un comentario."""
    if not comment_id:
        return {}
    for item in items:
        if not isinstance(item, dict):
            continue
        vm = _view_model(item)
        if vm and vm.get("commentId") == comment_id:
            return item
    return {}


def _token_de_respuestas(item: dict) -> dict | None:
    """Token de continuacion del hilo de respuestas de un comentario."""
    if not item:
        return None
    hilo = item.get("commentThreadRenderer") or {}
    respuestas = (hilo.get("replies") or {}).get("commentRepliesRenderer") or {}
    for contenido in respuestas.get("contents") or []:
        bloque = (contenido or {}).get("continuationItemRenderer") or {}
        endpoint = bloque.get("continuationEndpoint") or {}
        comando = endpoint.get("continuationCommand") or {}
        if comando.get("token"):
            return _consulta_continuacion(
                {"token": comando["token"], "click_tracking": endpoint.get("clickTrackingParams")}
            )
    return None


def _comentarios_de_items(items: list, entities: dict) -> list[dict]:
    """Traduce view models + entidad de payload a filas de comentario."""
    filas: list[dict] = []
    for item in items:
        vm = _view_model(item)
        if not vm:
            continue
        payload = _coincidir_entidad(entities, vm.get("commentKey", "")) or {}
        entidad = payload.get("commentEntityPayload") or {}
        props = entidad.get("properties") or {}
        contenido = (props.get("content") or {}).get("content") or ""
        if not contenido.strip():
            continue
        toolbar = entidad.get("toolbar") or {}
        autor = entidad.get("author") or {}
        filas.append(
            {
                "comment_id": props.get("commentId") or vm.get("commentId"),
                "autor": autor.get("displayName"),
                "autor_canal_id": autor.get("channelId"),
                "autor_es_creador": bool(autor.get("isCreator")),
                "texto": contenido.strip(),
                "publicado": props.get("publishedTime"),
                "likes": toolbar.get("likeCountNotliked"),
                "respuestas": toolbar.get("replyCount"),
                "nivel": props.get("replyLevel", 0),
            }
        )
    return filas


@dataclass
class ClienteYouTube:
    """Cliente HTTP de solo lectura contra la API interna de YouTube."""

    sesion: requests.Session = field(default_factory=requests.Session)
    pausar: float = PAUSA
    # Cache por video: `todo` reutiliza la ficha y la respuesta del reproductor
    # en lugar de pedirlas una vez por operacion.
    _html: dict = field(default_factory=dict, repr=False)
    _player: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.sesion.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            }
        )

    # -- infraestructura ---------------------------------------------------- #
    @staticmethod
    def _espera_429(respuesta: requests.Response) -> float:
        """Segundos a esperar ante HTTP 429: Retry-After numerico, acotado a 30 s.

        Retry-After tambien puede ser una fecha HTTP; en ese caso se usa la
        espera por defecto en lugar de fallar al convertir.
        """
        try:
            espera = float(respuesta.headers.get("Retry-After") or 10)
        except ValueError:
            espera = 10.0
        return min(max(espera, 0.0), 30.0)

    def _get(self, url: str, **kwargs) -> requests.Response:
        respuesta = self.sesion.get(url, timeout=TIMEOUT, **kwargs)
        if respuesta.status_code == 429:
            time.sleep(self._espera_429(respuesta))
            respuesta = self.sesion.get(url, timeout=TIMEOUT, **kwargs)
        return respuesta

    def _post(self, url: str, payload: dict) -> requests.Response:
        respuesta = self.sesion.post(url, json=payload, timeout=TIMEOUT)
        if respuesta.status_code == 429:
            time.sleep(self._espera_429(respuesta))
            respuesta = self.sesion.post(url, json=payload, timeout=TIMEOUT)
        return respuesta

    # -- paginas publicas ---------------------------------------------------- #
    def pagina_watch(self, video_id: str) -> str:
        """HTML publico de la ficha del video (una sola descarga por video)."""
        if video_id in self._html:
            return self._html[video_id]
        respuesta = self._get(f"https://www.youtube.com/watch?v={video_id}")
        if respuesta.status_code != 200:
            raise YouTubeError(
                f"No se pudo abrir la ficha del video (HTTP {respuesta.status_code}). "
                "Puede ser un video privado, restringido por edad o eliminado."
            )
        self._html[video_id] = respuesta.text
        return respuesta.text

    def clave_api(self, html: str) -> str:
        """Clave publica de InnerTube que la propia pagina publica."""
        m = re.search(r'"INNERTUBE_API_KEY":"([A-Za-z0-9_-]+)"', html)
        if not m:
            raise YouTubeError("La pagina no publico ninguna clave de API; YouTube cambio el HTML.")
        return m.group(1)

    def version_cliente(self, html: str) -> str:
        m = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
        return m.group(1) if m else CLIENT_WEB["clientVersion"]

    # -- API interna --------------------------------------------------------- #
    def reproductor(self, video_id: str, clave: str) -> dict:
        """Respuesta de youtubei/v1/player: metadatos y pistas de subtitulo."""
        if video_id in self._player:
            return self._player[video_id]
        payload = {
            "context": {"client": CLIENT_ANDROID},
            "videoId": video_id,
            "contentCheckOk": True,
            "racyCheckOk": True,
        }
        respuesta = self._post(f"https://www.youtube.com/youtubei/v1/player?key={clave}", payload)
        if respuesta.status_code != 200:
            raise YouTubeError(f"El reproductor respondio HTTP {respuesta.status_code}")
        datos = respuesta.json()
        estado = (datos.get("playabilityStatus") or {}).get("status")
        if estado not in (None, "OK"):
            motivo = (datos.get("playabilityStatus") or {}).get("reason") or estado
            raise YouTubeError(f"El video no es reproducible de forma anonima: {motivo}")
        self._player[video_id] = datos
        return datos

    def siguiente(self, clave: str, ctx: dict, **consulta) -> dict:
        """Respuesta de youtubei/v1/next (comentarios y continuaciones)."""
        payload = {"context": ctx, **consulta}
        respuesta = self._post(f"https://www.youtube.com/youtubei/v1/next?key={clave}", payload)
        if respuesta.status_code != 200:
            raise YouTubeError(f"youtubei/v1/next respondio HTTP {respuesta.status_code}")
        return respuesta.json()

    # -- operaciones de alto nivel ------------------------------------------- #
    def metadatos(self, video_id: str) -> dict:
        html = self.pagina_watch(video_id)
        player = extraer_respuesta_player(html)
        if not player:
            raise YouTubeError("No se encontro ytInitialPlayerResponse en la ficha del video.")
        datos = metadatos_desde_player(player)
        if not datos.get("titulo"):
            estado = datos.get("disponibilidad") or "desconocido"
            raise YouTubeError(
                f"El video no expone metadatos publicos (estado del reproductor: {estado}). "
                "Puede estar eliminado, ser privado o estar restringido por edad."
            )
        return datos

    def pistas_subtitulo(self, video_id: str) -> list[dict]:
        """Pistas de subtitulo disponibles (idioma, nombre y si es autodeclarada)."""
        html = self.pagina_watch(video_id)
        clave = self.clave_api(html)
        player = self.reproductor(video_id, clave)
        lista = (
            ((player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")
            or []
        )
        pistas = []
        for pista in lista:
            pistas.append(
                {
                    "idioma": pista.get("languageCode"),
                    "nombre": _texto_runs((pista.get("name") or {}).get("runs"))
                    or (pista.get("name") or {}).get("simpleText"),
                    "automatica": pista.get("kind") == "asr",
                    "traducible": bool(pista.get("isTranslatable")),
                    "base_url": pista.get("baseUrl"),
                }
            )
        return pistas

    def transcripcion(self, video_id: str, idioma: str | None = None) -> dict:
        """Texto de la transcripcion con marca de tiempo por segmento."""
        html = self.pagina_watch(video_id)
        clave = self.clave_api(html)
        player = self.reproductor(video_id, clave)
        lista = (
            ((player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")
            or []
        )
        if not lista:
            raise YouTubeError("El video no expone transcripcion (subtitulos desactivados).")
        elegida = None
        if idioma:
            for pista in lista:
                if pista.get("languageCode") == idioma:
                    elegida = pista
                    break
            if elegida is None:
                disponibles = ", ".join(sorted({p.get("languageCode", "?") for p in lista}))
                raise YouTubeError(
                    f"No hay subtitulos en {idioma!r}; disponibles: {disponibles}"
                )
        else:
            elegida = _elegir_pista(lista)
        base = elegida.get("baseUrl")
        if not base:
            raise YouTubeError("La pista de subtitulos no trae URL de descarga.")
        respuesta = self._get(base)
        if respuesta.status_code != 200 or not respuesta.content:
            raise YouTubeError(
                "YouTube no devolvio el archivo de subtitulos (posible requisito de PO token, proof of origin). "
                "Usar yt-dlp como alternativa."
            )
        segmentos = segmentos_desde_timedtext(respuesta.text)
        if not segmentos:
            raise YouTubeError("El archivo de subtitulos venia vacio.")
        return {
            "video_id": video_id,
            "idioma": elegida.get("languageCode"),
            "automatica": elegida.get("kind") == "asr",
            "segmentos": segmentos,
            "texto": " ".join(s["texto"] for s in segmentos),
        }

    def _continuaciones_items(self, respuesta: dict) -> list[dict]:
        items: list[dict] = []
        for endpoint in respuesta.get("onResponseReceivedEndpoints") or []:
            for clave in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
                bloque = endpoint.get(clave)
                if isinstance(bloque, dict):
                    items.extend(bloque.get("continuationItems") or [])
        return items

    @staticmethod
    def _entidades(respuesta: dict) -> dict:
        entidades: dict = {}
        for mutacion in (
            ((respuesta.get("frameworkUpdates") or {}).get("entityBatchUpdate") or {}).get("mutations") or []
        ):
            clave = mutacion.get("entityKey")
            payload = mutacion.get("payload") or {}
            if clave and "commentEntityPayload" in payload:
                entidades[clave] = payload
        return entidades

    def comentarios(
        self,
        video_id: str,
        maximo: int = 200,
        con_respuestas: bool = False,
        orden: str = "newest",
    ) -> dict:
        """Comentarios de primer nivel (y opcionalmente sus respuestas).

        La ordenacion se pide con el token de clasificacion que publica la
        propia pagina ("Destacados" o "Mas recientes"); el resto de la
        paginacion se encadena por tokens de continuacion.

        "Destacados" es la jerarquia de la interfaz y devuelve un subconjunto;
        "Mas recientes" recorre la lista completa de comentarios del video.
        """
        html = self.pagina_watch(video_id)
        clave = self.clave_api(html)
        version = self.version_cliente(html)
        ctx = {"client": {**CLIENT_WEB, "clientVersion": version, "hl": "es", "gl": "ES"}}
        datos = extraer_datos_iniciales(html)
        seccion = _buscar_seccion_comentarios(datos)
        if not seccion:
            raise YouTubeError("La pagina no expone la seccion de comentarios del video.")
        tokens = _tokens_continuacion(seccion)
        if not tokens:
            raise YouTubeError("No se hallo token de paginacion de comentarios.")
        consulta = _consulta_continuacion(tokens[0])

        filas: list[dict] = []
        hilos_respuesta: list[tuple[str, dict]] = []
        vistos: set[str] = set()
        vistos_tokens: set[str] = set()
        declarados: int | None = None
        paginas = 0
        while consulta and len(filas) < maximo and paginas < 60:
            token = consulta["continuation"]
            if token in vistos_tokens:
                break
            vistos_tokens.add(token)
            respuesta = self.siguiente(clave, ctx, **consulta)
            paginas += 1
            items = self._continuaciones_items(respuesta)
            entidades = self._entidades(respuesta)

            cabecera = next(
                (i.get("commentsHeaderRenderer") for i in items if "commentsHeaderRenderer" in i), None
            )
            if cabecera:
                declarados = _contar_comentarios(cabecera)
                if orden in {"top", "newest"}:
                    consulta_orden = _token_de_orden(cabecera, orden)
                    if consulta_orden and consulta_orden["continuation"] not in vistos_tokens:
                        # se reinicia la carga con el token del criterio pedido
                        consulta = consulta_orden
                        filas.clear()
                        vistos.clear()
                        vistos_tokens.add(consulta["continuation"])
                        respuesta = self.siguiente(clave, ctx, **consulta)
                        paginas += 1
                        items = self._continuaciones_items(respuesta)
                        entidades = self._entidades(respuesta)

            nuevas = _comentarios_de_items(items, entidades)
            for fila in nuevas:
                cid = fila.get("comment_id")
                if cid and cid in vistos:
                    continue
                if cid:
                    vistos.add(cid)
                filas.append(fila)
                if con_respuestas:
                    token_respuesta = _token_de_respuestas(item_por_id(items, cid))
                    if token_respuesta:
                        hilos_respuesta.append((cid, token_respuesta))

            consulta = _siguiente_consulta(items)
            time.sleep(self.pausar)

        if con_respuestas and hilos_respuesta:
            filas.extend(self._respuestas(clave, ctx, hilos_respuesta))
        filas = filas[:maximo]
        return {
            "video_id": video_id,
            "orden": orden,
            "comentarios_declarados": declarados,
            "obtenidos": len(filas),
            "comentarios": filas,
        }

    def _respuestas(self, clave: str, ctx: dict, hilos: list[tuple[str, dict]]) -> list[dict]:
        """Descarga las respuestas de cada hilo, paginando dentro del hilo."""
        filas: list[dict] = []
        for parent_id, consulta in hilos:
            actual = consulta
            vistos_tokens: set[str] = set()
            while actual:
                token = actual["continuation"]
                if token in vistos_tokens:
                    break
                vistos_tokens.add(token)
                try:
                    respuesta = self.siguiente(clave, ctx, **actual)
                except YouTubeError:
                    break
                items = self._continuaciones_items(respuesta)
                entidades = self._entidades(respuesta)
                for fila in _comentarios_de_items(items, entidades):
                    fila["respuesta_a"] = parent_id
                    fila["nivel"] = 1
                    filas.append(fila)
                actual = _siguiente_consulta(items)
                time.sleep(self.pausar)
        return filas


# --------------------------------------------------------------------------- #
# Escritura de resultados
# --------------------------------------------------------------------------- #
def _escribir_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)


COLUMNAS_COMENTARIOS = [
    "comment_id",
    "respuesta_a",
    "autor",
    "autor_canal_id",
    "autor_es_creador",
    "texto",
    "publicado",
    "likes",
    "respuestas",
    "nivel",
]
COLUMNAS_SEGMENTOS = ["inicio", "duracion", "texto"]


def _sello() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _arg_comunes(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", required=True, help="URL del video o ID de 11 caracteres")
    parser.add_argument("--out", default="datos", help="Carpeta de salida (por defecto: datos)")
    parser.add_argument("--json", dest="solo_json", action="store_true", help="No escribir CSV")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_meta = sub.add_parser("metadatos", help="Metadatos del video")
    _arg_comunes(p_meta)

    p_tr = sub.add_parser("transcripcion", help="Transcripcion con marca de tiempo")
    _arg_comunes(p_tr)
    p_tr.add_argument("--lang", help="Codigo de idioma (por defecto: subtitulo manual o el primero)")

    p_com = sub.add_parser("comentarios", help="Comentarios del video")
    _arg_comunes(p_com)
    p_com.add_argument("--max", dest="maximo", type=int, default=200, help="Maximo de comentarios")
    p_com.add_argument("--con-respuestas", action="store_true", help="Incluir respuestas a comentarios")
    p_com.add_argument(
        "--orden",
        choices=["newest", "top"],
        default="newest",
        help="Criterio: newest recorre la lista completa; top usa la jerarquia de la interfaz",
    )

    p_todo = sub.add_parser("todo", help="Metadatos, transcripcion y comentarios")
    _arg_comunes(p_todo)
    p_todo.add_argument("--max", dest="maximo", type=int, default=200)
    p_todo.add_argument("--lang")
    p_todo.add_argument("--con-respuestas", action="store_true")

    args = parser.parse_args(argv)
    try:
        video_id = extraer_id_video(args.url)
    except YouTubeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    cliente = ClienteYouTube()
    salida = Path(args.out)
    try:
        if args.comando == "metadatos":
            datos = cliente.metadatos(video_id)
            datos["capturado_en_utc"] = _sello()
            datos["fuente"] = "youtube.com/watch (ytInitialPlayerResponse)"
            _escribir_json(salida / f"{video_id}_metadatos.json", datos)
            print(json.dumps(datos, ensure_ascii=False, indent=2))
            return 0

        if args.comando == "transcripcion":
            datos = cliente.transcripcion(video_id, args.lang)
            datos["capturado_en_utc"] = _sello()
            _escribir_json(salida / f"{video_id}_transcripcion.json", datos)
            if not args.solo_json:
                _escribir_csv(
                    salida / f"{video_id}_transcripcion.csv", datos["segmentos"], COLUMNAS_SEGMENTOS
                )
            print(
                f"transcripcion: {len(datos['segmentos'])} segmentos "
                f"(idioma {datos['idioma']}, automatica={datos['automatica']})"
            )
            return 0

        if args.comando == "comentarios":
            datos = cliente.comentarios(
                video_id,
                maximo=args.maximo,
                con_respuestas=args.con_respuestas,
                orden=args.orden,
            )
            datos["capturado_en_utc"] = _sello()
            _escribir_json(salida / f"{video_id}_comentarios.json", datos)
            if not args.solo_json:
                _escribir_csv(
                    salida / f"{video_id}_comentarios.csv",
                    datos["comentarios"],
                    COLUMNAS_COMENTARIOS,
                )
            print(
                f"comentarios: {datos['obtenidos']} de {datos['comentarios_declarados']} declarados"
            )
            return 0

        if args.comando == "todo":
            datos = cliente.metadatos(video_id)
            datos["capturado_en_utc"] = _sello()
            _escribir_json(salida / f"{video_id}_metadatos.json", datos)
            try:
                tr = cliente.transcripcion(video_id, args.lang)
                tr["capturado_en_utc"] = _sello()
                _escribir_json(salida / f"{video_id}_transcripcion.json", tr)
                if not args.solo_json:
                    _escribir_csv(
                        salida / f"{video_id}_transcripcion.csv", tr["segmentos"], COLUMNAS_SEGMENTOS
                    )
            except YouTubeError as exc:
                tr = {"video_id": video_id, "error": str(exc)}
                _escribir_json(salida / f"{video_id}_transcripcion.json", tr)
            try:
                com = cliente.comentarios(
                    video_id, maximo=args.maximo, con_respuestas=args.con_respuestas
                )
                com["capturado_en_utc"] = _sello()
                _escribir_json(salida / f"{video_id}_comentarios.json", com)
                if not args.solo_json:
                    _escribir_csv(
                        salida / f"{video_id}_comentarios.csv",
                        com["comentarios"],
                        COLUMNAS_COMENTARIOS,
                    )
            except YouTubeError as exc:
                com = {"video_id": video_id, "error": str(exc)}
                _escribir_json(salida / f"{video_id}_comentarios.json", com)
            print(json.dumps(datos, ensure_ascii=False, indent=2))
            print(f"transcripcion: {'error' if 'error' in tr else str(len(tr['segmentos'])) + ' segmentos'}")
            print(f"comentarios: {'error' if 'error' in com else str(com['obtenidos'])}")
            return 0
    except YouTubeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"error de red: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
