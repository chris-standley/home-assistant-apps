"""The web server: the page, the maps and photo reading.

Scoring itself runs in the page (static/scoring.js), on the phone.

All URLs are relative so the page works both through Home Assistant ingress
(under /api/hassio_ingress/<token>/) and on the app's own port.
"""

from __future__ import annotations

import json
import logging
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import vision
from .homeassistant import AIUnavailable, HomeAssistant
from .maps import all_maps, get_map

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD = 20 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "TicketToRide"
    ha: HomeAssistant  # set by make_server

    def log_message(self, fmt: str, *args) -> None:  # route through logging
        log.debug("%s %s", self.address_string(), fmt % args)

    # -- helpers ------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), "application/json")

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            raise ValueError("That photo is too big.")
        return self.rfile.read(length) if length else b""

    # -- routes -------------------------------------------------------------

    def do_GET(self) -> None:
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path == "/sw.js":  # served from the root so it covers the whole page
            return self._static("sw.js")
        if path.startswith("/static/"):
            return self._static(path[len("/static/") :])
        if path == "/api/status":
            entities = self.ha.ai_entities()
            return self._json(
                {
                    "ai": self.ha.available,
                    "ai_task_entity": self.ha.ai_task_entity,
                    "ai_entities": entities,
                }
            )
        if path == "/api/maps":
            return self._json([{"id": m.id, "name": m.name} for m in all_maps().values()])
        if path.startswith("/api/maps/"):
            try:
                return self._json(get_map(path[len("/api/maps/") :]).to_json())
            except KeyError as err:
                return self._error(str(err), 404)
        self._error("Not found", 404)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            body = self._body()
        except ValueError as err:
            return self._error(str(err), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)

        if url.path in ("/api/read-board", "/api/read-tickets"):
            try:
                game_map = get_map(query.get("map", "usa"))
            except KeyError as err:
                return self._error(str(err), 404)
            if not body:
                return self._error("No photo was sent.")
            try:
                if url.path == "/api/read-board":
                    colors = [c for c in query.get("players", "").split(",") if c in game_map.player_colors]
                    colors = colors or game_map.player_colors
                    text = self.ha.read_image(
                        body, "Read Ticket to Ride board", vision.board_instructions(game_map, colors)
                    )
                    log.debug("Board answer: %s", text)
                    return self._json(vision.parse_board(game_map, colors, text))
                text = self.ha.read_image(body, "Read Ticket to Ride tickets", vision.tickets_instructions(game_map))
                log.debug("Tickets answer: %s", text)
                return self._json({"tickets": vision.parse_tickets(game_map, text)})
            except AIUnavailable as err:
                return self._error(str(err), HTTPStatus.SERVICE_UNAVAILABLE)
            except (ValueError, json.JSONDecodeError) as err:
                log.warning("Couldn't understand the AI's answer: %s", err)
                return self._error("The AI's answer didn't make sense. Try another photo, or mark it by hand.", 502)

        self._error("Not found", 404)

    def _static(self, name: str) -> None:
        target = (STATIC_DIR / name).resolve()
        if STATIC_DIR.resolve() not in target.parents or not target.is_file():
            return self._error("Not found", 404)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)


def make_server(ha: HomeAssistant, host: str = "0.0.0.0", port: int = 8099) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"ha": ha})
    return ThreadingHTTPServer((host, port), handler)
