"""Near-identical shots get stacked; similar shots of a scene don't fill an album."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import cv2
import numpy as np

from immich_memories import analysis
from immich_memories.analysis import Analysis, similarity
from immich_memories.curate import STRICTNESS, Group, group_similar, select
from immich_memories.events import Event
from immich_memories.immich import Person
from immich_memories.naming import gather_facts, name_event
from test_memories import JACK, _photo


def scene(seed: int, w: int = 640, h: int = 480) -> np.ndarray:
    """A made-up photo: a coloured gradient sky and ground with some shapes."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.uint8)
    top, bottom = rng.integers(0, 255, 3), rng.integers(0, 255, 3)
    for y in range(h):
        img[y] = top + (bottom - top) * y / h
    for _ in range(8):
        colour = [int(c) for c in rng.integers(0, 255, 3)]
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        if rng.random() < 0.5:
            cv2.circle(img, (x, y), int(rng.integers(20, 90)), colour, -1)
        else:
            cv2.rectangle(img, (x, y), (x + int(rng.integers(30, 160)), y + int(rng.integers(30, 160))), colour, -1)
    return cv2.GaussianBlur(img, (0, 0), 1.5)


def reframe(img: np.ndarray, shift: float = 0.0, zoom: float = 0.0, brighter: float = 1.0) -> np.ndarray:
    h, w = img.shape[:2]
    dx, dz = int(w * shift), int(min(h, w) * zoom / 2)
    out = img[dz : h - dz, dz + dx : w - dz]
    out = cv2.resize(out, (w, h))
    return cv2.convertScaleAbs(out, alpha=brighter)


def look(img: np.ndarray, sharpness: float = 100.0) -> Analysis:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return Analysis(sharpness, 0.9, analysis._dhash(gray), [], analysis._hist(img), analysis._layout(img))


T0 = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)


def shot(i: int, seconds: float) -> object:
    return _photo(id=str(i), utc_dt=T0 + timedelta(seconds=seconds), local_dt=(T0 + timedelta(seconds=seconds)).replace(tzinfo=None))


def test_similarity_scale():
    a = scene(1)
    assert similarity(look(a), look(reframe(a, shift=0.05))) > 0.85
    assert similarity(look(a), look(reframe(a, zoom=0.1, brighter=1.1))) > 0.7
    for other in range(2, 8):
        assert similarity(look(a), look(scene(other))) < 0.5


def test_reframed_shots_minutes_apart_are_stacked():
    a, b = scene(1), scene(2)
    looks = {
        "0": look(a), "1": look(reframe(a, shift=0.04)), "2": look(reframe(a, shift=0.08, brighter=1.05)),
        "3": look(b),  # something else, straight after
    }
    photos = [shot(0, 0), shot(1, 40), shot(2, 150), shot(3, 160)]
    groups = sorted(sorted(p.id for p in g) for g in group_similar(photos, looks))
    assert groups == [["0", "1", "2"], ["3"]]


def test_strictness_changes_how_far_apart_shots_can_be():
    a = scene(1)
    looks = {"0": look(a), "1": look(reframe(a, shift=0.05))}
    photos = [shot(0, 0), shot(1, 10 * 60)]  # ten minutes apart
    assert len(group_similar(photos, looks, STRICTNESS["normal"])) == 2
    assert len(group_similar(photos, looks, STRICTNESS["strong"])) == 1


def test_album_takes_one_photo_of_a_scene_shot_over_half_an_hour():
    # Ten photos of the same view, a few minutes apart and reframed each time
    # (not stacked: too far apart), and ten different scenes.
    base = scene(1)
    same = [(shot(i, i * 200), look(reframe(base, shift=0.02 * (i % 4), zoom=0.03 * (i % 3)))) for i in range(10)]
    other = [(shot(100 + i, 4000 + i * 600), look(scene(10 + i))) for i in range(10)]
    looks = {p.id: a for p, a in same + other}
    groups = [Group([p], p) for p, _ in same + other]
    scores = {p.id: 1.0 for p, _ in same + other}
    chosen = select(groups, scores, max_photos=50, analyses=looks)
    same_ids = {p.id for p, _ in same}
    assert sum(p.id in same_ids for p in chosen) == 1
    assert sum(p.id not in same_ids for p in chosen) >= 8


def test_ai_title_calling_a_party_a_birthday_is_ignored():
    photos = [_photo(id=str(i), people=[Person(JACK["id"], "Jack")]) for i in range(30)]
    event = Event("spike", date(2026, 2, 14), date(2026, 2, 14), photos, tags=["party"])
    facts = gather_facts(event, set())
    prompts = []

    def ai(prompt):
        prompts.append(prompt)
        return "Jack's birthday February 2026"

    name, how = name_event(event, facts, ai=ai)
    assert how == "template" and "birthday" not in name.lower()
    assert name.startswith("Party with Jack")
    assert "Jack's 5th birthday" not in prompts[0]


def test_ai_title_for_a_real_birthday_is_kept():
    event = Event("birthday", date(2026, 6, 20), date(2026, 6, 20), [_photo()], person="Jack", age=7)
    name, how = name_event(event, gather_facts(event, set()), ai=lambda p: "Jack's 7th birthday party")
    assert (name, how) == ("Jack's 7th birthday party", "ai")
