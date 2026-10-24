"""Entry point: read the app's options and serve the web page."""

from __future__ import annotations

import json
import logging
import os
import sys

from .homeassistant import HomeAssistant
from .maps import all_maps
from .server import make_server

log = logging.getLogger("ticket_to_ride")


def main() -> None:
    options_path = os.environ.get("OPTIONS_PATH", "/data/options.json")
    try:
        with open(options_path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raw = {}
    logging.basicConfig(
        level=getattr(logging, str(raw.get("log_level", "info")).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    ha = HomeAssistant(ai_task_entity=(raw.get("ai_task_entity") or "").strip() or None)
    maps = all_maps()
    port = int(os.environ.get("PORT", "8099"))
    server = make_server(ha, port=port)
    log.info("Maps: %s", ", ".join(m.name for m in maps.values()))
    if ha.available:
        log.info("Photos are read by %s", ha.ai_task_entity or "Home Assistant's default AI Task entity")
    else:
        log.info("Not running under Home Assistant: photo reading is off, routes can be marked by hand")
    log.info("Ready on port %d", port)
    server.serve_forever()


if __name__ == "__main__":
    main()
