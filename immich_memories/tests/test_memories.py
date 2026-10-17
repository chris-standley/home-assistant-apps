"""End-to-end tests against a fake Immich library.

Run from immich_memories/: `PYTHONPATH=app python -m pytest tests`
"""

from __future__ import annotations

import itertools
import uuid
from datetime import date, datetime, timedelta, timezone

import cv2
import numpy as np
import pytest

from immich_memories.analysis import Analysis, Face
from immich_memories.clutter import clutter_reason, is_screenshot
from immich_memories.curate import group_similar, pick_best
from immich_memories.events import DetectSettings, detect_events
from immich_memories.immich import Person, Photo, photo_from_asset
from immich_memories.labels import LabelIndex
from immich_memories.naming import clean_ai_title, gather_facts, template_name
from immich_memories.runner import Options, run

HOME = (53.80, -1.55)  # Leeds
EMMA = {"id": "p-emma", "name": "Emma"}
JACK = {"id": "p-jack", "name": "Jack", "birthDate": "2019-07-20"}
CHRIS = {"id": "p-chris", "name": "Chris"}

PLACES = {
    "leeds": (53.80, -1.55, "Leeds", "England", "United Kingdom"),
    "ambleside": (54.43, -2.96, "Ambleside", "England", "United Kingdom"),
    "barcelona": (41.38, 2.17, "Barcelona", "Catalonia", "Spain"),
    "marseille": (43.30, 5.37, "Marseille", "Provence-Alpes-Côte d'Azur", "France"),
    "rome": (41.90, 12.50, "Rome", "Lazio", "Italy"),
    "dubrovnik": (42.65, 18.09, "Dubrovnik", "Dubrovnik-Neretva", "Croatia"),
    "athens": (37.98, 23.73, "Athens", "Attica", "Greece"),
    "keswick": (54.60, -3.13, "Keswick", "England", "United Kingdom"),
    "bergen": (60.39, 5.32, "Bergen", "Vestland", "Norway"),
    "tromso": (69.65, 18.96, "Tromsø", "Troms", "Norway"),
}

_counter = itertools.count()


def asset(when: datetime, place: str | None = "leeds", people=(), name=None, make="Apple", mime="image/jpeg",
          w=4032, h=3024, dup=None, fav=False):
    lat = lon = city = state = country = None
    if place:
        lat, lon, city, state, country = PLACES[place]
    n = next(_counter)
    return {
        "id": str(uuid.UUID(int=n + 1)),
        "type": "IMAGE",
        "checksum": f"c{n}",
        "localDateTime": when.isoformat() + "Z",
        "fileCreatedAt": when.replace(tzinfo=timezone.utc).isoformat(),
        "originalFileName": name or f"IMG_{n:04d}.HEIC",
        "originalMimeType": mime,
        "isFavorite": fav,
        "isTrashed": False,
        "isArchived": False,
        "visibility": "timeline",
        "duplicateId": dup,
        "width": w,
        "height": h,
        "exifInfo": {
            "latitude": lat, "longitude": lon, "city": city, "state": state, "country": country,
            "make": make, "model": "iPhone" if make else None, "exifImageWidth": w, "exifImageHeight": h,
        },
        "people": [dict(p) for p in people],
    }


def every(start: datetime, count: int, minutes: int = 20, **kw):
    return [asset(start + timedelta(minutes=minutes * i), **kw) for i in range(count)]


def build_library():
    lib = []
    # Background: a few photos a day at home through 2024.
    d = datetime(2024, 1, 2, 19, 7)
    while d < datetime(2024, 12, 20):
        lib += every(d, 2, place="leeds")
        d += timedelta(days=3)
    # A Mediterranean cruise in May: a port a day.
    for i, port in enumerate(["barcelona", "marseille", "rome", "dubrovnik", "athens"]):
        lib += every(datetime(2024, 5, 11 + i, 9), 12, minutes=30, place=port, people=[EMMA] if i % 2 else [])
    # A walk in the Lake District with Emma (a Saturday in June).
    lib += every(datetime(2024, 6, 8, 10), 20, minutes=12, place="ambleside", people=[EMMA, CHRIS])
    # Jack's birthday party at home.
    lib += every(datetime(2024, 7, 20, 13), 15, minutes=10, place="leeds", people=[JACK])
    # Christmas at home, with one burst of near-identical shots.
    lib += every(datetime(2024, 12, 25, 9), 14, minutes=25, place="leeds", people=[EMMA, JACK])
    burst = datetime(2024, 12, 25, 16)
    lib += [asset(burst + timedelta(seconds=i), place="leeds", people=[EMMA, JACK]) for i in range(4)]
    # A busy day at home with no holiday: lots of garden photos.
    lib += every(datetime(2024, 9, 14, 10), 40, minutes=6, place="leeds")
    # Clutter that must never appear: screenshots, receipts, a leaking pipe.
    lib.append(asset(datetime(2024, 5, 12, 20), place=None, make=None, mime="image/png", name="IMG_9001.PNG", w=1179, h=2556))
    lib.append(asset(datetime(2024, 12, 25, 11), place=None, name="Screenshot 2024-12-25 at 11.00.00.png", make=None, mime="image/png"))
    receipts = [asset(datetime(2024, 9, 14, 18, i), place="leeds") for i in range(3)]
    lib += receipts
    return lib, {a["id"] for a in receipts}


class FakeImmich:
    def __init__(self, assets, labels=None):
        self.assets = assets
        self.labels = labels or {}
        self.albums_made: list[dict] = []
        self.stacks: dict[str, list[str]] = {}
        self.covers = {}

    def all_photos(self, taken_after=None):
        return [p for p in (photo_from_asset(a) for a in self.assets) if p]

    def smart_search_ids(self, query, limit):
        for key, ids in self.labels.items():
            if key in query:
                return list(ids)[:limit]
        return []

    def people(self):
        return [EMMA, JACK, CHRIS]

    def preview(self, asset_id):
        # A sharp checkerboard, blurred more for later photos in a burst.
        rng = np.random.default_rng(int(uuid.UUID(asset_id)) % 1000)
        img = (rng.random((240, 320)) * 255).astype(np.uint8)
        img = cv2.GaussianBlur(img, (0, 0), 0.5 + (int(uuid.UUID(asset_id)) % 4))
        return cv2.imencode(".jpg", img)[1].tobytes()

    def albums(self):
        return [{"id": a["id"], "albumName": a["name"], "description": a["description"]} for a in self.albums_made]

    def create_album(self, name, description, asset_ids):
        album = {"id": f"album-{len(self.albums_made)}", "name": name, "description": description, "assets": asset_ids}
        self.albums_made.append(album)
        return album

    def set_album_cover(self, album_id, asset_id):
        self.covers[album_id] = asset_id

    def create_stack(self, ids):
        sid = f"stack-{len(self.stacks)}"
        self.stacks[sid] = ids
        return sid

    def add_to_album(self, album_id, asset_ids):
        album = next(a for a in self.albums_made if a["id"] == album_id)
        album["assets"] = album["assets"] + [i for i in asset_ids if i not in album["assets"]]

    def delete_album(self, album_id):
        self.albums_made = [a for a in self.albums_made if a["id"] != album_id]

    def delete_stack(self, stack_id):
        self.stacks.pop(stack_id, None)


class FakeHA:
    available = True

    def __init__(self, ai_reply=None):
        self.ai_reply = ai_reply
        self.prompts = []

    def find_immich(self):
        return list(getattr(self, "discovered", []))

    def core_config(self):
        return {"latitude": HOME[0], "longitude": HOME[1], "country": "GB"}

    def ai_generate(self, prompt, entity, agent):
        self.prompts.append(prompt)
        return self.ai_reply(prompt) if self.ai_reply else None


class StubAnalyzer:
    """Avoids needing the YuNet model in unit tests: sharpness from the image only."""

    def analyse(self, data):
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        return Analysis(
            sharpness=float(cv2.Laplacian(img, cv2.CV_64F).var()),
            exposure=0.9,
            dhash=0,
            faces=[],
        )


@pytest.fixture(autouse=True)
def no_yunet(monkeypatch):
    monkeypatch.setattr("immich_memories.runner.Analyzer", StubAnalyzer)


def test_full_run_makes_expected_memories(tmp_path):
    lib, receipts = build_library()
    immich = FakeImmich(lib, labels={"receipt": receipts})
    made = run(Options(immich_api_key="x"), FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    names = {m["name"] for m in made}
    assert "Mediterranean cruise 2024" not in names  # no cruise label in this library
    assert "Mediterranean trip 2024" in names
    assert "Day out in Ambleside with Emma & Chris" in names
    assert "Jack's 5th birthday" in names
    assert "Christmas 2024" in names
    assert any(n.startswith("Day in Leeds, September 2024") for n in names)

    every_album_asset = {a for album in immich.albums_made for a in album["assets"]}
    by_id = {a["id"]: a for a in lib}
    assert not every_album_asset & receipts, "receipts must be left out"
    assert not any(by_id[a]["originalMimeType"] == "image/png" for a in every_album_asset), "no screenshots"
    # The Christmas burst became one stack, and only its best shot is in the album.
    assert len(immich.stacks) == 1
    for ids in immich.stacks.values():
        assert ids[0] in every_album_asset
        assert not set(ids[1:]) & every_album_asset
    assert all("Made by Immich Memories" in a["description"] for a in immich.albums_made)


def test_rerun_is_idempotent_and_respects_deleted_albums(tmp_path):
    lib, receipts = build_library()
    immich = FakeImmich(lib, labels={"receipt": receipts})
    opts = Options(immich_api_key="x")
    first = run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    immich.delete_album(immich.albums_made[0]["id"])
    second = run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    assert first and second == []


def test_undo_removes_albums_and_stacks(tmp_path):
    lib, receipts = build_library()
    immich = FakeImmich(lib, labels={"receipt": receipts})
    run(Options(immich_api_key="x"), FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    assert immich.albums_made and immich.stacks
    run(Options(immich_api_key="x", remove_created=True), FakeHA(), data_dir=str(tmp_path), immich=immich)
    assert immich.albums_made == [] and immich.stacks == {}


def test_dry_run_changes_nothing(tmp_path):
    lib, _ = build_library()
    immich = FakeImmich(lib)
    made = run(Options(immich_api_key="x", dry_run=True), FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    assert made and immich.albums_made == [] and immich.stacks == {}


def test_ai_names_are_used_and_cleaned(tmp_path):
    lib, _ = build_library()
    immich = FakeImmich(lib)
    ha = FakeHA(ai_reply=lambda p: '"Walk in the Lake District with Emma."' if "Ambleside" in p else "Title: Something")
    made = run(Options(immich_api_key="x"), ha, data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    names = {m["name"]: m["named_by"] for m in made}
    assert names.get("Walk in the Lake District with Emma") == "ai"
    assert "Day by day:" in next(p for p in ha.prompts if "Barcelona" in p)


def test_ai_failure_falls_back_to_templates(tmp_path):
    lib, _ = build_library()
    immich = FakeImmich(lib)
    ha = FakeHA(ai_reply=lambda p: None)
    made = run(Options(immich_api_key="x"), ha, data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    assert all(m["named_by"] == "template" for m in made)
    assert len(ha.prompts) == 1  # gave up after the first failure


def test_cruise_label_names_a_cruise():
    lib, _ = build_library()
    photos = [p for p in (photo_from_asset(a) for a in lib) if p]
    events = detect_events(photos, DetectSettings(home=HOME, country="GB"), today=date(2025, 1, 1))
    trip = next(e for e in events if e.kind == "trip")
    trip.tags = ["cruise"]
    assert template_name(trip, gather_facts(trip, set())) == "Mediterranean cruise 2024"


def test_events_leave_recent_days_to_settle():
    lib, _ = build_library()
    photos = [p for p in (photo_from_asset(a) for a in lib) if p]
    events = detect_events(photos, DetectSettings(home=HOME, country="GB"), today=date(2024, 12, 26))
    assert not any(e.holiday == "Christmas" for e in events)


def _photo(**kw):
    base = dict(
        id="a", local_dt=datetime(2024, 1, 1), utc_dt=datetime(2024, 1, 1, tzinfo=timezone.utc), filename="IMG_1.JPG",
        mime="image/jpeg", width=4000, height=3000, is_favorite=False, rating=0, lat=None, lon=None, city=None,
        state=None, country=None, make="Apple", model="iPhone",
    )
    base.update(kw)
    return Photo(**base)


def test_screenshot_and_clutter_rules():
    assert is_screenshot(_photo(filename="Screenshot_20240101-101010.jpg"))
    assert is_screenshot(_photo(make=None, model=None, mime="image/png"))
    assert is_screenshot(_photo(make=None, model=None, width=1179, height=2556))
    assert not is_screenshot(_photo())
    labels = LabelIndex({"household_job": {"a", "b"}, "document": {"c"}})
    assert clutter_reason(_photo(id="a"), labels) == "household_job"
    assert clutter_reason(_photo(id="c"), labels) == "document"
    # Someone in the shot: keep it even if it looks a bit like a DIY job.
    assert clutter_reason(_photo(id="b", people=[Person("p", "Emma")]), labels) is None


def test_best_shot_prefers_people_looking_with_eyes_open_then_sharpness():
    shots = [_photo(id=i) for i in "abc"]
    looking, away, blink = Face(0.2, 1.0, 1.0, 300, True), Face(0.2, 0.2, 1.0, 300, False), Face(0.2, 1.0, 0.0, 300, False)
    analyses = {
        # Sharpest, but one of the two people is looking away.
        "a": Analysis(sharpness=900, exposure=0.9, dhash=0, faces=[looking, Face(0.2, 0.2, 1.0, 900, False)]),
        # Both looking at the camera with eyes open, a little softer.
        "b": Analysis(sharpness=600, exposure=0.9, dhash=0, faces=[looking, Face(0.2, 1.0, 1.0, 600, True)]),
        # Both facing the camera but one blinking.
        "c": Analysis(sharpness=650, exposure=0.9, dhash=0, faces=[looking, blink]),
    }
    assert pick_best(shots, analyses).id == "b"
    # Same expressions: the sharpest wins.
    analyses["a"] = Analysis(sharpness=900, exposure=0.9, dhash=0, faces=[looking, Face(0.2, 1.0, 1.0, 900, True)])
    assert pick_best(shots, analyses).id == "a"
    assert away.looking < looking.looking


def test_group_similar_uses_time_and_look():
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ps = [_photo(id=str(i), utc_dt=t + timedelta(seconds=s)) for i, s in enumerate([0, 1, 30, 400])]
    analyses = {
        "0": Analysis(1, 1, 0b1111, []),
        "1": Analysis(1, 1, 0b1110, []),
        "2": Analysis(1, 1, 0b1111, []),  # 30s later but looks the same
        "3": Analysis(1, 1, 0b1111, []),  # same look, but much later: a new moment
    }
    groups = sorted(len(g) for g in group_similar(ps, analyses))
    assert groups == [1, 3]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"Mediterranean cruise 2024"', "Mediterranean cruise 2024"),
        ("Title: Walk in the Lake District with Emma.", "Walk in the Lake District with Emma"),
        ("Sorry, I can't help with that", None),
        ("", None),
        ("x" * 80, None),
    ],
)
def test_clean_ai_title(raw, expected):
    assert clean_ai_title(raw) == expected
