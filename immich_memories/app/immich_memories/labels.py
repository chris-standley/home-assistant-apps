"""Scene labels from Immich's smart search (CLIP).

Immich's smart search ranks the whole library by similarity to a text query
but doesn't return a score. So for each label we take the top slice of the
library and treat membership of that slice as "this photo looks like <label>".
That gives three things:

- clutter to leave out: screenshots, receipts and paperwork, jobs around the
  house (only when no-one is in the photo);
- photos to favour: scenery and landmarks;
- what an event was about (beach, hiking, snow, a wedding...), which feeds
  album names.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Label:
    key: str
    query: str
    share: float  # fraction of the library to treat as matching
    kind: str  # "clutter", "highlight" or "scene"


LABELS = [
    # Clutter: excluded unless someone is in the photo.
    Label("screenshot", "a screenshot of a phone or computer screen", 0.04, "clutter"),
    Label("document", "a receipt, invoice, letter or document with printed text", 0.03, "clutter"),
    Label("paperwork", "a photo of paperwork, a form, a label or a serial number plate", 0.02, "clutter"),
    Label(
        "household_job",
        "DIY home repair job: pipes, wiring, boiler, damp wall, broken appliance, tools, floorboards",
        0.03,
        "clutter",
    ),
    Label("whiteboard", "a whiteboard, notes or a screen photographed for reference", 0.01, "clutter"),
    # Highlights: favoured when choosing photos.
    Label("scenery", "a beautiful landscape view with scenery", 0.06, "highlight"),
    Label("landmark", "a famous landmark, monument, cathedral or historic building", 0.04, "highlight"),
    Label("sunset", "a sunset or sunrise sky", 0.02, "highlight"),
    # Scenes: what the event was about.
    Label("beach", "people on a sandy beach by the sea", 0.03, "scene"),
    Label("hiking", "walking on a footpath in hills, mountains or countryside", 0.03, "scene"),
    Label("lake", "a lake surrounded by hills", 0.02, "scene"),
    Label("snow", "snow, skiing or snowboarding", 0.02, "scene"),
    Label("city", "sightseeing in a city street", 0.03, "scene"),
    Label("cruise", "the deck of a cruise ship at sea", 0.01, "scene"),
    Label("theme_park", "rides at a theme park", 0.01, "scene"),
    Label("zoo", "animals at a zoo or safari park", 0.01, "scene"),
    Label("wedding", "a wedding with a bride and groom", 0.01, "scene"),
    Label("birthday", "a birthday party with a cake and candles", 0.01, "scene"),
    Label("christmas", "a Christmas tree, decorations and presents", 0.01, "scene"),
    Label("concert", "a live concert or festival stage", 0.01, "scene"),
    Label("camping", "camping with a tent", 0.01, "scene"),
    Label("garden", "flowers in a garden", 0.02, "scene"),
]

MIN_SLICE = 100
MAX_SLICE = 4000


class LabelIndex:
    """{label key: set of asset ids} for the library, built once per run."""

    def __init__(self, sets: dict[str, set[str]]):
        self.sets = sets

    @classmethod
    def build(cls, immich, library_size: int, enabled: bool = True) -> "LabelIndex":
        sets: dict[str, set[str]] = {}
        if not enabled:
            return cls(sets)
        for label in LABELS:
            limit = int(min(MAX_SLICE, max(MIN_SLICE, library_size * label.share)))
            try:
                sets[label.key] = set(immich.smart_search_ids(label.query, limit))
            except Exception as err:
                log.warning(
                    "Smart search failed for %r (is smart search enabled in Immich?): %s", label.key, err
                )
                return cls({})
        log.info("Smart search labels ready (%d labels)", len(sets))
        return cls(sets)

    def has(self, asset_id: str, key: str) -> bool:
        return asset_id in self.sets.get(key, ())

    def kinds(self, asset_id: str, kind: str) -> list[str]:
        return [l.key for l in LABELS if l.kind == kind and asset_id in self.sets.get(l.key, ())]

    def scene_tags(self, asset_ids: list[str], min_share: float = 0.2, min_count: int = 3) -> list[str]:
        """Scene/highlight labels that describe a good share of an event's photos."""
        tags = []
        n = len(asset_ids)
        for label in LABELS:
            if label.kind == "clutter":
                continue
            s = self.sets.get(label.key)
            if not s or not n:
                continue
            hits = sum(1 for a in asset_ids if a in s)
            if hits >= min_count and hits / n >= min_share:
                tags.append((hits / n, label.key))
        return [k for _, k in sorted(tags, reverse=True)]
