import json
import threading
import urllib.error
import urllib.request

import pytest

from ticket_to_ride.homeassistant import AIUnavailable
from ticket_to_ride.server import make_server


class FakeHA:
    available = True
    ai_task_entity = "ai_task.test"

    def __init__(self):
        self.calls = []
        self.reply = '{"routes": [{"id": "denver-santa_fe", "player": "red"}]}'

    def ai_entities(self):
        return ["ai_task.test"]

    def read_image(self, image, task_name, instructions):
        self.calls.append((image, task_name, instructions))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def server():
    ha = FakeHA()
    srv = make_server(ha, host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", ha
    srv.shutdown()


def call(url, data=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype} if data else {})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type")
    except urllib.error.HTTPError as err:
        return err.code, err.read(), err.headers.get("Content-Type")


def test_page_and_static(server):
    base, _ = server
    status, body, ctype = call(base + "/")
    assert status == 200 and b"<html" in body and ctype.startswith("text/html")
    assert call(base + "/static/app.js")[0] == 200
    assert call(base + "/static/scoring.js")[0] == 200
    assert call(base + "/sw.js")[0] == 200
    assert call(base + "/static/../server.py")[0] == 404


def test_maps(server):
    base, _ = server
    maps = json.loads(call(base + "/api/maps")[1])
    assert {m["id"] for m in maps} >= {"usa", "europe"}
    usa = json.loads(call(base + "/api/maps/usa")[1])
    assert len(usa["routes"]) == 100
    assert call(base + "/api/maps/nope")[0] == 404


def test_read_board(server):
    base, ha = server
    status, body, _ = call(base + "/api/read-board?map=usa&players=red,blue", b"\xff\xd8jpeg", "image/jpeg")
    assert status == 200
    assert json.loads(body)["routes"] == {"denver-santa_fe": "red"}
    image, task, instructions = ha.calls[0]
    assert image == b"\xff\xd8jpeg"
    assert "red, blue" in instructions


def test_read_tickets(server):
    base, ha = server
    ha.reply = '{"tickets": [{"id": "boston-miami"}]}'
    status, body, _ = call(base + "/api/read-tickets?map=usa", b"jpeg", "image/jpeg")
    assert status == 200
    assert json.loads(body)["tickets"][0]["points"] == 12


def test_read_errors(server):
    base, ha = server
    ha.reply = AIUnavailable("No AI Task entity is set up.")
    status, body, _ = call(base + "/api/read-board?map=usa", b"jpeg", "image/jpeg")
    assert status == 503 and "No AI Task" in json.loads(body)["error"]
    ha.reply = "I can't see a board."
    assert call(base + "/api/read-board?map=usa", b"jpeg", "image/jpeg")[0] == 502
    assert call(base + "/api/read-board?map=usa", b"", "image/jpeg")[0] == 400
