import json

import pytest
import requests

from ticket_to_ride.homeassistant import AIUnavailable, HomeAssistant


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_read_image_sends_attachment_and_cleans_up(tmp_path, monkeypatch):
    ha = HomeAssistant(token="t", ai_task_entity="ai_task.claude", media_dir=str(tmp_path))
    seen = {}

    def post(url, json=None, timeout=None):
        seen["url"], seen["json"] = url, json
        name = json["attachments"][0]["media_content_id"].rsplit("/", 1)[1]
        seen["saved"] = (tmp_path / "ticket_to_ride" / name).read_bytes()
        return FakeResponse(200, {"service_response": {"data": '{"routes": []}'}})

    monkeypatch.setattr(ha.session, "post", post)
    assert ha.read_image(b"photo", "task", "look") == '{"routes": []}'
    assert seen["url"].endswith("/core/api/services/ai_task/generate_data?return_response")
    assert seen["json"]["entity_id"] == "ai_task.claude"
    assert seen["json"]["attachments"][0]["media_content_id"].startswith(
        "media-source://media_source/local/ticket_to_ride/"
    )
    assert seen["saved"] == b"photo"
    assert list((tmp_path / "ticket_to_ride").iterdir()) == []


def test_read_image_errors(tmp_path, monkeypatch):
    with pytest.raises(AIUnavailable):
        HomeAssistant(token="").read_image(b"x", "t", "i")
    ha = HomeAssistant(token="t", media_dir=str(tmp_path))
    monkeypatch.setattr(ha.session, "post", lambda *a, **k: FakeResponse(500, {"message": "boom"}))
    with pytest.raises(AIUnavailable, match="HTTP 500"):
        ha.read_image(b"x", "t", "i")

    def fail(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(ha.session, "post", fail)
    with pytest.raises(AIUnavailable, match="Couldn't reach"):
        ha.read_image(b"x", "t", "i")
