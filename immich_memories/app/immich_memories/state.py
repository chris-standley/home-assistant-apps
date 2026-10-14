"""What this app has made, so reruns don't repeat it and it can all be undone."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

MARKER = "Made by Immich Memories"


class State:
    def __init__(self, path: str):
        self.path = path
        self.data = {"version": 1, "events": {}}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        self.data.setdefault("events", {})

    @property
    def events(self) -> dict[str, dict]:
        return self.data["events"]

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def overlaps(self, start: date, end: date) -> bool:
        """Whether an event in this date range has already been handled."""
        for rec in self.events.values():
            if rec.get("status") == "dry_run":
                continue
            s, e = date.fromisoformat(rec["start"]), date.fromisoformat(rec["end"])
            if s <= end and start <= e:
                return True
        return False

    def record(self, key: str, **fields) -> None:
        fields.setdefault("updated_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        self.events[key] = {**self.events.get(key, {}), **fields}
