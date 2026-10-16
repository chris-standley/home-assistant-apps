"""A tiny HTTP server that speaks enough of the Immich API to exercise the real client.

Used by test_http.py; can also be run by hand (`python tests/fake_immich_server.py 2283`)
to point the app at during development.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

API_KEY = "test-key"


def make_handler(fake):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body=None, raw=None, ctype="application/json"):
            data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _route(self, method):
            url = urlparse(self.path)
            path, query = url.path, parse_qs(url.query)
            if path == "/api/server/version":
                return self._send(200, {"major": 3, "minor": 3, "patch": 0})
            if self.headers.get("x-api-key") != API_KEY:
                return self._send(401, {"message": "Invalid API key"})
            body = self._body() if method in ("POST", "PUT", "PATCH", "DELETE") else {}
            if path == "/api/users/me":
                return self._send(200, {"id": "u1"})
            if path == "/api/search/metadata":
                items = [a for a in fake.assets]
                start = int(body.get("cursor") or 0)
                size = body.get("size", 250)
                page = items[start : start + size]
                nxt = str(start + size) if start + size < len(items) else None
                return self._send(200, {"assets": {"items": page, "nextCursor": nxt, "nextPage": None, "count": len(page), "total": len(items), "facets": []}, "albums": {}})
            if path == "/api/search/smart":
                ids = fake.smart_search_ids(body["query"], body.get("size", 250))
                items = [{"id": i} for i in ids]
                return self._send(200, {"assets": {"items": items, "nextPage": None, "count": len(items), "total": len(items), "facets": []}, "albums": {}})
            if path == "/api/people":
                return self._send(200, {"people": fake.people(), "hasNextPage": False, "total": 3, "hidden": 0})
            if path.startswith("/api/assets/") and path.endswith("/thumbnail"):
                return self._send(200, raw=fake.preview(path.split("/")[3]), ctype="image/jpeg")
            if path == "/api/albums" and method == "GET":
                return self._send(200, fake.albums())
            if path == "/api/albums" and method == "POST":
                a = fake.create_album(body["albumName"], body.get("description", ""), body.get("assetIds", []))
                return self._send(201, {"id": a["id"], "albumName": a["name"]})
            if path.startswith("/api/albums/") and method == "PATCH":
                fake.set_album_cover(path.split("/")[3], body["albumThumbnailAssetId"])
                return self._send(200, {})
            if path.startswith("/api/albums/") and path.endswith("/assets") and method == "PUT":
                fake.add_to_album(path.split("/")[3], body["ids"])
                return self._send(200, [{"id": i, "success": True} for i in body["ids"]])
            if path.startswith("/api/albums/") and method == "DELETE":
                fake.delete_album(path.split("/")[3])
                return self._send(204)
            if path == "/api/stacks" and method == "POST":
                return self._send(201, {"id": fake.create_stack(body["assetIds"])})
            if path.startswith("/api/stacks/") and method == "DELETE":
                fake.delete_stack(path.split("/")[3])
                return self._send(204)
            return self._send(404, {"message": f"no route {method} {path}"})

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PATCH(self):
            self._route("PATCH")

        def do_PUT(self):
            self._route("PUT")

        def do_DELETE(self):
            self._route("DELETE")

    return Handler


def serve(fake, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(fake))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from test_memories import FakeImmich, build_library

    lib, receipts = build_library()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2283
    srv = serve(FakeImmich(lib, labels={"receipt": receipts}), port)
    print(f"Fake Immich on http://127.0.0.1:{port} (API key {API_KEY})")
    threading.Event().wait()
