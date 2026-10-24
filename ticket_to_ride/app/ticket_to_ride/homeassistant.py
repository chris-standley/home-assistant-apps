"""Asking Home Assistant's AI to look at a photo, through the Supervisor.

Photos are saved to Home Assistant's media folder (this app maps /media) and
passed to `ai_task.generate_data` as attachments, so any AI Task entity that
can see images works: Claude, OpenAI, Google Gemini, Ollama with a vision
model, and so on.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"


class AIUnavailable(RuntimeError):
    """No AI is set up, or it couldn't read the photo."""


class HomeAssistant:
    def __init__(
        self,
        token: str | None = None,
        ai_task_entity: str | None = None,
        media_dir: str | None = None,
        timeout: float = 180,
    ):
        self.token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")
        self.ai_task_entity = ai_task_entity or None
        self.media_dir = Path(media_dir or os.environ.get("MEDIA_DIR", "/media")) / "ticket_to_ride"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.token)

    def ai_entities(self) -> list[str]:
        """AI Task entities Home Assistant knows about, for the status line."""
        if not self.available:
            return []
        try:
            resp = self.session.get(f"{SUPERVISOR}/core/api/states", timeout=15)
            resp.raise_for_status()
            return [s["entity_id"] for s in resp.json() if s.get("entity_id", "").startswith("ai_task.")]
        except (requests.RequestException, ValueError) as err:
            log.debug("Could not list AI Task entities: %s", err)
            return []

    def read_image(self, image: bytes, task_name: str, instructions: str) -> str:
        """Ask the AI about one JPEG photo and return its text answer."""
        if not self.available:
            raise AIUnavailable("This app isn't running under Home Assistant, so there's no AI to read photos.")
        self.media_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}.jpg"
        path = self.media_dir / name
        path.write_bytes(image)
        try:
            data: dict[str, Any] = {
                "task_name": task_name,
                "instructions": instructions,
                "attachments": [
                    {
                        # Home Assistant's default "local" media source is /media.
                        "media_content_id": f"media-source://media_source/local/ticket_to_ride/{name}",
                        "media_content_type": "image/jpeg",
                    }
                ],
            }
            if self.ai_task_entity:
                data["entity_id"] = self.ai_task_entity
            try:
                resp = self.session.post(
                    f"{SUPERVISOR}/core/api/services/ai_task/generate_data?return_response",
                    json=data,
                    timeout=self.timeout,
                )
            except requests.RequestException as err:
                raise AIUnavailable(f"Couldn't reach Home Assistant: {err}") from err
            if resp.status_code >= 400:
                log.warning("ai_task.generate_data failed: HTTP %s %s", resp.status_code, resp.text[:500])
                raise AIUnavailable(_explain(resp.status_code, resp.text))
            out = (resp.json() or {}).get("service_response") or {}
            text = out.get("data")
            if not isinstance(text, str) or not text.strip():
                raise AIUnavailable("The AI didn't answer.")
            return text
        finally:
            try:
                path.unlink()
            except OSError:
                pass


def _explain(status: int, body: str) -> str:
    low = body.lower()
    if "attachment" in low or ("media" in low and "not" in low):
        return "Your AI Task entity can't take photos. Pick one with a vision model in this app's settings."
    if "entity" in low and ("not found" in low or "no default" in low or "default" in low):
        return (
            "No AI Task entity is set up. Add an AI integration (e.g. Anthropic, OpenAI or Google) in Home "
            "Assistant, or name the entity in this app's settings."
        )
    return f"Home Assistant's AI returned an error (HTTP {status})."
