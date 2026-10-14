"""Talking to Home Assistant through the Supervisor.

Used for three things: Home Assistant's home location, time zone and country
(to tell trips from days at home and to pick public holidays), finding the
Immich app on the same server, and asking whichever AI Home Assistant has
configured to polish album names.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)

SUPERVISOR = "http://supervisor"

# Ports the Immich server listens on inside its container, across the common
# Immich apps (2283 is current upstream; 3001 was used before v1.118; 8080 by
# some community packages).
IMMICH_PORTS = (2283, 3001, 8080)


class HomeAssistant:
    def __init__(self, token: str | None = None, timeout: float = 30):
        self.token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _get(self, path: str) -> Any:
        resp = self.session.get(f"{SUPERVISOR}{path}", timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # Supervisor endpoints wrap results in {"result": "ok", "data": ...};
        # the Core API proxy (/core/api/...) does not.
        if isinstance(data, dict) and "result" in data and "data" in data:
            return data["data"]
        return data

    # -- core config --------------------------------------------------------

    def core_config(self) -> dict:
        if not self.available:
            return {}
        try:
            return self._get("/core/api/config")
        except requests.RequestException as err:
            log.warning("Could not read Home Assistant's configuration: %s", err)
            return {}

    # -- Immich discovery ---------------------------------------------------

    def find_immich(self) -> list[str]:
        """Candidate URLs for an Immich app installed on this Home Assistant."""
        if not self.available:
            return []
        try:
            addons = self._get("/addons").get("addons", [])
        except requests.RequestException as err:
            log.debug("Could not list apps: %s", err)
            return []
        urls: list[str] = []
        for addon in addons:
            if "immich" not in addon.get("slug", "").lower():
                continue
            if "memories" in addon.get("slug", "").lower():
                continue  # that's us
            if addon.get("state") not in (None, "started"):
                log.info("Found the %s app, but it isn't running", addon.get("name"))
            try:
                info = self._get(f"/addons/{addon['slug']}/info")
            except requests.RequestException as err:
                log.debug("Could not read %s info: %s", addon["slug"], err)
                info = {}
            host = info.get("hostname") or addon["slug"].replace("_", "-")
            container_ports = []
            for key, host_port in (info.get("network") or {}).items():
                port = int(str(key).split("/")[0])
                if info.get("host_network"):
                    container_ports.append((port, port))
                else:
                    container_ports.append((port, host_port))
            preferred = sorted(
                container_ports, key=lambda p: IMMICH_PORTS.index(p[0]) if p[0] in IMMICH_PORTS else 99
            )
            if info.get("host_network"):
                # Apps on the host network are reached through the Docker gateway.
                urls += [f"http://172.30.32.1:{p}" for p, _ in preferred]
            else:
                urls += [f"http://{host}:{p}" for p, _ in preferred]
                for _, host_port in preferred:
                    if host_port:
                        urls.append(f"http://172.30.32.1:{host_port}")
            if info.get("ingress_port"):
                urls.append(f"http://{host}:{info['ingress_port']}")
            urls += [f"http://{host}:{p}" for p in IMMICH_PORTS]
        # De-duplicate, keeping order.
        return list(dict.fromkeys(urls))

    # -- AI --------------------------------------------------------------

    def _service(self, domain: str, service: str, data: dict) -> dict:
        resp = self.session.post(
            f"{SUPERVISOR}/core/api/services/{domain}/{service}?return_response",
            json=data,
            timeout=120,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"{domain}.{service}: HTTP {resp.status_code} {resp.text[:200]}")
        return resp.json().get("service_response") or {}

    def ai_generate(self, instructions: str, ai_task_entity: str | None, conversation_agent: str | None) -> str | None:
        """Ask Home Assistant's AI for text.

        Tries `ai_task.generate_data` (Home Assistant 2025.8+, uses the default
        AI task entity unless one is named), then `conversation.process` with
        the configured conversation agent. Returns None if neither works.
        """
        if not self.available:
            return None
        errors = []
        if ai_task_entity != "none":
            data: dict[str, Any] = {"task_name": "Immich memory album name", "instructions": instructions}
            if ai_task_entity:
                data["entity_id"] = ai_task_entity
            try:
                out = self._service("ai_task", "generate_data", data)
                text = out.get("data")
                if isinstance(text, str) and text.strip():
                    return text
            except (requests.RequestException, RuntimeError, ValueError) as err:
                errors.append(str(err))
        if conversation_agent:
            try:
                out = self._service(
                    "conversation", "process", {"text": instructions, "agent_id": conversation_agent}
                )
                speech = out.get("response", {}).get("speech", {}).get("plain", {}).get("speech")
                if out.get("response", {}).get("response_type") != "error" and speech:
                    return speech
                errors.append(f"conversation agent replied: {speech!r}")
            except (requests.RequestException, RuntimeError, ValueError) as err:
                errors.append(str(err))
        if errors:
            log.debug("AI naming unavailable: %s", "; ".join(errors))
        return None
