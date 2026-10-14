"""Telling photos worth remembering from screenshots, receipts and DIY snaps."""

from __future__ import annotations

import re

from .immich import Photo
from .labels import LabelIndex

SCREENSHOT_NAME = re.compile(
    r"(screen ?shot|screenshot|screen_recording|screenrecording|^scr_|^scrn|capture d.?[ée]cran|bildschirmfoto)",
    re.IGNORECASE,
)

# Common phone/tablet/monitor screen sizes (portrait and landscape). A PNG or
# camera-less image at exactly one of these sizes is almost always a screenshot.
SCREEN_SIZES = {
    (w, h)
    for a, b in [
        (750, 1334), (828, 1792), (1080, 1920), (1080, 2340), (1080, 2400), (1125, 2436),
        (1170, 2532), (1179, 2556), (1206, 2622), (1242, 2208), (1242, 2688), (1284, 2778),
        (1290, 2796), (1320, 2868), (1440, 2560), (1440, 3040), (1440, 3088), (1440, 3200),
        (1536, 2048), (1620, 2160), (1640, 2360), (1668, 2224), (1668, 2388), (2048, 2732),
        (1366, 768), (1440, 900), (1920, 1080), (2560, 1440), (2560, 1600), (2880, 1800),
        (3024, 1964), (3456, 2234), (3840, 2160),
    ]
    for w, h in ((a, b), (b, a))
}


def is_screenshot(p: Photo) -> bool:
    if SCREENSHOT_NAME.search(p.filename):
        return True
    no_camera = not p.make and not p.model
    if no_camera and p.mime == "image/png":
        return True
    if no_camera and (p.width, p.height) in SCREEN_SIZES:
        return True
    return False


def clutter_reason(p: Photo, labels: LabelIndex) -> str | None:
    """Why a photo should be left out of memories, or None if it's a keeper."""
    if is_screenshot(p):
        return "screenshot"
    no_camera = not p.make and not p.model
    if labels.has(p.id, "screenshot") and (no_camera or not p.people):
        return "screenshot"
    if p.people:
        # Someone's in it, so it's probably not just a receipt or a boiler.
        return None
    for key in ("document", "paperwork", "household_job", "whiteboard"):
        if labels.has(p.id, key):
            return key
    return None
