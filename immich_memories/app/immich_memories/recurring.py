"""Collections: albums that gather a recurring kind of memory and grow each year.

- Seasons: *Christmas through the years*, *Easter through the years*... from
  every holiday memory (and trips over that holiday), plus any memory whose
  name mentions the season ("Festive lights in York", "Xmas market").
- Birthdays: *Jack's birthdays*.
- Countries: *Holidays in Norway*, from every trip mostly spent in a country
  other than home.
- Places: *Trips to the Lake District*, from trips and days out whose photos
  centre within a few kilometres of each other (the AI names the area; the
  fallback is the most visited town).

A collection appears once there are enough memories of its kind (two by
default). Each run adds the highlights of new memories to it. Photos you remove
from a collection aren't added back, and a deleted collection isn't recreated.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .events import haversine_km
from .naming import clean_ai_title
from .state import MARKER, State

log = logging.getLogger(__name__)

PLACE_RADIUS_KM = 30
SEASONS = {"Christmas", "Easter", "Halloween", "New Year's Eve", "Bonfire Night", "Mother's Day", "Father's Day"}
# Words in a memory's name that put it in a season's collection.
SEASON_WORDS = {
    "Christmas": r"christmas|x-?mas|festive|yule(tide)?|advent|santa|nativity|carol(s|ling)?|boxing day|christmas eve",
    "Easter": r"easter",
    "Halloween": r"hallowe'?en|trick or treat",
    "New Year's Eve": r"new year'?s? eve|hogmanay",
    "Bonfire Night": r"bonfire night|guy fawkes",
    "Mother's Day": r"mother'?s day|mothering sunday",
    "Father's Day": r"father'?s day",
}
_SEASON_RE = {season: re.compile(rf"\b({words})\b", re.I) for season, words in SEASON_WORDS.items()}


def season_of(record: dict) -> str | None:
    """The season a memory belongs to: its holiday, or a season its name mentions."""
    if record.get("holiday") in SEASONS:
        return record["holiday"]
    name = record.get("name") or ""
    return next((season for season, rx in _SEASON_RE.items() if rx.search(name)), None)


@dataclass
class Collection:
    key: str
    kind: str  # season, birthdays, country, place
    name: str
    members: list[str]  # event keys
    towns: list[str] = field(default_factory=list)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _live(state: State) -> dict[str, dict]:
    """Event records whose albums exist (made, or would be in a dry run)."""
    return {
        k: r for k, r in state.events.items()
        if r.get("status") in ("created", "dry_run") and r.get("highlights")
    }


def plan(state: State, home_country: str | None, min_members: int = 2) -> list[Collection]:
    events = _live(state)
    out: list[Collection] = []

    seasons: dict[str, list[str]] = {}
    birthdays: dict[str, list[str]] = {}
    countries: dict[str, list[str]] = {}
    places: list[tuple[str, dict]] = []
    for key, r in sorted(events.items(), key=lambda kv: kv[1]["start"]):
        season = season_of(r)
        if season:
            seasons.setdefault(season, []).append(key)
        if r.get("kind") == "birthday" and r.get("person"):
            birthdays.setdefault(r["person"], []).append(key)
        if r.get("kind") == "trip" and r.get("country") and r["country"] != home_country:
            countries.setdefault(r["country"], []).append(key)
        elif r.get("kind") in ("trip", "day_out") and r.get("centre"):
            places.append((key, r))

    def distinct_years(keys):
        return len({events[k]["start"][:4] for k in keys})

    for holiday, keys in seasons.items():
        if distinct_years(keys) >= min_members:
            out.append(Collection(f"season:{_slug(holiday)}", "season", f"{holiday} through the years", keys))
    for person, keys in birthdays.items():
        if len(keys) >= min_members:
            out.append(Collection(f"birthdays:{_slug(person)}", "birthdays", f"{person}'s birthdays", keys))
    for country, keys in countries.items():
        if len(keys) >= min_members:
            out.append(Collection(f"country:{_slug(country)}", "country", f"Holidays in {country}", keys))

    # Places: join visits whose centres are close (single linkage).
    clusters: list[list[tuple[str, dict]]] = []
    for key, r in places:
        centre = tuple(r["centre"])
        joined = [c for c in clusters if any(haversine_km(centre, tuple(o["centre"])) <= PLACE_RADIUS_KM for _, o in c)]
        merged = [(key, r)] + [m for c in joined for m in c]
        clusters = [c for c in clusters if c not in joined] + [merged]
    for cluster in clusters:
        if len(cluster) < min_members:
            continue
        towns = Counter(t for _, r in cluster for t in r.get("towns", []))
        top = [t for t, _ in towns.most_common(8)]
        name = f"Trips to {top[0]}" if top else "Favourite places"
        keys = sorted(k for k, _ in cluster)
        out.append(Collection(f"place:{keys[0]}", "place", name, keys, towns=top))
    return out


PLACE_PROMPT = """You name photo albums that collect every visit to one place, like Apple Photos memories.

Examples: "Trips to the Lake District", "Days out in the Peak District", "Weekends in Cornwall", "Visits to Edinburgh".

These visits were all to the same area. Towns visited, most visited first: {towns}.
Name the album using the best-known name for the area (for example a national park, coast, island or city). \
Start with "Trips to", "Days out in", "Weekends in" or "Visits to". Keep it under 40 characters. \
Reply with the name only."""


def update(
    immich,
    state: State,
    home_country: str | None,
    ai: Callable[[str], str | None] | None,
    dry_run: bool,
    min_members: int = 2,
) -> list[dict]:
    """Create new collections and top up existing ones. Returns what changed."""
    store: dict[str, dict] = state.data.setdefault("collections", {})
    existing_albums = None if dry_run else {a["id"] for a in immich.albums()}
    events = _live(state)
    changes = []

    for col in plan(state, home_country, min_members):
        # A place cluster keeps its album as it grows, even though its key
        # (its earliest visit) may change when an older visit appears.
        rec = store.get(col.key)
        if rec is None and col.kind == "place":
            for k, r in store.items():
                if r.get("kind") == "place" and set(r.get("members", [])) & set(col.members):
                    rec = r
                    break
        if rec and rec.get("status") == "dismissed":
            continue
        if rec and existing_albums is not None and rec.get("album_id") and rec["album_id"] not in existing_albums:
            rec["status"] = "dismissed"
            log.info("Collection %r was deleted in Immich; it won't be made again", rec.get("name"))
            continue

        wanted = [a for k in col.members for a in events[k]["highlights"]]
        added = set(rec.get("added", [])) if rec else set()
        new_ids = [a for a in dict.fromkeys(wanted) if a not in added]

        if rec is None:
            name = col.name
            if col.kind == "place" and ai is not None and col.towns:
                name = clean_ai_title(ai(PLACE_PROMPT.format(towns=", ".join(col.towns)))) or name
            used = {r.get("name") for r in store.values()}
            if name in used:
                name = f"{name} ({col.members[0].split(':')[1][:4]})"
            if dry_run:
                log.info("[dry run] Would make collection %r with %d photos", name, len(new_ids))
                changes.append({"collection": name, "added": len(new_ids), "new": True})
                continue
            first = date.fromisoformat(events[col.members[0]]["start"]).year
            album = immich.create_album(name, f"Since {first}\n\n{MARKER}", new_ids)
            store[col.key] = {
                "kind": col.kind, "name": name, "album_id": album["id"], "status": "created",
                "members": col.members, "added": new_ids,
            }
            log.info("Made collection %r with %d photos", name, len(new_ids))
            changes.append({"collection": name, "added": len(new_ids), "new": True})
        else:
            rec["members"] = sorted(set(rec.get("members", [])) | set(col.members))
            if not new_ids:
                continue
            if dry_run:
                log.info("[dry run] Would add %d photos to %r", len(new_ids), rec["name"])
            else:
                immich.add_to_album(rec["album_id"], new_ids)
                rec["added"] = list(added | set(new_ids))
                log.info("Added %d photos to %r", len(new_ids), rec["name"])
            changes.append({"collection": rec["name"], "added": len(new_ids), "new": False})
        state.save()
    state.save()
    return changes


def summarise_event(photos, chosen, scores, highlights: int = 12) -> dict:
    """What collections need to remember about an event's album."""
    gps = [(p.lat, p.lon) for p in photos if p.has_gps]
    centre = None
    if gps:
        centre = [round(sum(x for x, _ in gps) / len(gps), 4), round(sum(y for _, y in gps) / len(gps), 4)]
    countries = Counter(p.country for p in photos if p.country)
    country = None
    if countries:
        c, n = countries.most_common(1)[0]
        if n / sum(countries.values()) >= 0.6:
            country = c
    towns = [t for t, _ in Counter(p.city for p in photos if p.city).most_common(5)]
    best = sorted(chosen, key=lambda p: scores.get(p.id, 0), reverse=True)[:highlights]
    return {
        "centre": centre,
        "country": country,
        "towns": towns,
        "highlights": [p.id for p in sorted(best, key=lambda p: p.local_dt)],
    }
