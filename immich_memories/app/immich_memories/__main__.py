"""Entry point: read the app's options, run now and then once a day."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

from .homeassistant import HomeAssistant
from .runner import Options, run

log = logging.getLogger("immich_memories")


def seconds_until(run_time: str) -> float:
    hour, minute = (int(x) for x in run_time.split(":"))
    now = datetime.now()
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def main() -> None:
    options_path = os.environ.get("OPTIONS_PATH", "/data/options.json")
    with open(options_path, encoding="utf-8") as f:
        raw = json.load(f)
    logging.basicConfig(
        level=getattr(logging, str(raw.get("log_level", "info")).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    opts = Options.from_dict(raw)
    if not opts.immich_api_key:
        log.error("Add an Immich API key in this app's configuration, then restart it.")
        sys.exit(1)
    run_time = raw.get("run_time", "03:30")
    ha = HomeAssistant()
    data_dir = os.environ.get("DATA_DIR", "/data")

    first = True
    while True:
        if not first or raw.get("run_on_start", True):
            try:
                made = run(opts, ha, data_dir=data_dir)
                log.info("Run finished: %d new %s", len(made), "memory" if len(made) == 1 else "memories")
            except SystemExit as err:
                log.error("%s", err)
            except Exception:
                log.exception("Run failed; trying again at the next scheduled time")
        first = False
        wait = seconds_until(run_time)
        log.info("Next run at %s", (datetime.now() + timedelta(seconds=wait)).strftime("%Y-%m-%d %H:%M"))
        time.sleep(wait)


if __name__ == "__main__":
    main()
