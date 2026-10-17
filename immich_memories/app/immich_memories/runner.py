"""One pass: find new memories in Immich and turn them into albums."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from .analysis import AnalysisCache, Analyzer, analyse_photos
from .clutter import clutter_reason
from .curate import make_groups, pick_cover, score_photos, select
from .events import DetectSettings, detect_events, guess_home, haversine_km
from .homeassistant import HomeAssistant
from .immich import Immich, ImmichError, pin_host
from .labels import LabelIndex
from .naming import describe, gather_facts, name_event
from .recurring import summarise_event, update as update_collections
from .state import MARKER, State

log = logging.getLogger(__name__)


@dataclass
class Options:
    immich_url: str = ""
    immich_ip: str = ""
    verify_ssl: bool = True
    immich_api_key: str = ""
    dry_run: bool = False
    ai_names: bool = True
    ai_task_entity: str = ""
    conversation_agent: str = ""
    create_stacks: bool = True
    max_photos_per_album: int = 50
    max_albums_per_run: int = 20
    min_photos_trip: int = 15
    min_photos_holiday: int = 10
    min_photos_spike: int = 25
    spike_factor: float = 3.0
    home_radius_km: float = 40
    holiday_country: str = ""
    holiday_subdivision: str = ""
    exclude_people_from_names: list[str] = field(default_factory=list)
    earliest_date: str = ""
    collections: bool = True
    min_memories_for_collection: int = 2
    remove_created: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Options":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and v is not None}
        return cls(**known)


def connect(opts: Options, ha: HomeAssistant) -> Immich:
    candidates = []
    if opts.immich_url:
        candidates.append(opts.immich_url)
        host = urlparse(opts.immich_url if "://" in opts.immich_url else f"http://{opts.immich_url}").hostname
        if opts.immich_ip and host:
            pin_host(host, opts.immich_ip)
            log.info("Connecting to %s at %s", host, opts.immich_ip)
    # The Immich app on this Home Assistant, directly: also the fallback when
    # the configured URL can't be reached from inside Home Assistant.
    candidates += [u for u in ha.find_immich() if u not in candidates]
    if not candidates:
        raise SystemExit(
            "Couldn't find an Immich app on this Home Assistant. Set 'Immich URL' in this app's configuration."
        )
    errors = []
    for url in candidates:
        client = Immich(url, opts.immich_api_key, timeout=15, verify=opts.verify_ssl)
        try:
            version = client.version()
        except ImmichError as err:
            errors.append(f"{url}: {err}")
            continue
        try:
            client.check_auth()
        except ImmichError as err:
            raise SystemExit(f"Immich at {url} rejected the API key: {err}") from err
        client.timeout = 120
        log.info("Connected to Immich %s at %s", version, url)
        if opts.immich_url and url != opts.immich_url:
            log.warning("Couldn't use %s, so connected to the Immich app directly instead", opts.immich_url)
        return client
    raise SystemExit("Couldn't reach Immich. Tried:\n  " + "\n  ".join(errors))


def undo(immich: Immich, state: State, dry_run: bool) -> None:
    """Delete every album and stack this app created."""
    albums = {a["id"]: a for a in immich.albums()}
    album_ids = {r["album_id"] for r in state.events.values() if r.get("album_id")}
    album_ids |= {i for i, a in albums.items() if MARKER in (a.get("description") or "")}
    stack_ids = {s for r in state.events.values() for s in r.get("stacks", [])}
    log.info("Removing %d albums and %d stacks made by this app", len(album_ids), len(stack_ids))
    if dry_run:
        return
    for album_id in album_ids:
        if album_id in albums:
            immich.delete_album(album_id)
    for stack_id in stack_ids:
        try:
            immich.delete_stack(stack_id)
        except ImmichError as err:
            log.debug("Stack %s already gone: %s", stack_id, err)
    state.data["events"] = {}
    state.data["collections"] = {}
    state.save()
    log.info("Done. Turn 'Remove created albums' off again to start making memories.")


def run(opts: Options, ha: HomeAssistant, data_dir: str = "/data", today: date | None = None, immich: Immich | None = None) -> list[dict]:
    """Returns a record for each album made (or that would be made, in a dry run)."""
    immich = immich or connect(opts, ha)
    state = State(f"{data_dir}/state.json")

    if opts.remove_created:
        undo(immich, state, opts.dry_run)
        return []

    # Albums the user deleted stay deleted: remember them as dismissed.
    existing = {a["id"] for a in immich.albums()}
    for rec in state.events.values():
        if rec.get("status") == "created" and rec.get("album_id") not in existing:
            rec["status"] = "dismissed"
            log.info("Album %r was deleted in Immich; it won't be made again", rec.get("name"))
    state.save()

    ha_config = ha.core_config()
    country = opts.holiday_country or ha_config.get("country") or ""
    home = None
    if ha_config.get("latitude") is not None and ha_config.get("longitude") is not None:
        home = (float(ha_config["latitude"]), float(ha_config["longitude"]))

    after = datetime.fromisoformat(opts.earliest_date) if opts.earliest_date else None
    photos = immich.all_photos(taken_after=after)
    log.info("Found %d photos in Immich", len(photos))
    if not photos:
        return []

    labels = LabelIndex.build(immich, len(photos))

    keep, dropped = [], Counter()
    for p in photos:
        if p.is_stack_child:
            continue  # its stack's cover photo stands in for it
        reason = clutter_reason(p, labels)
        if reason:
            dropped[reason] += 1
        else:
            keep.append(p)
    if dropped:
        log.info("Leaving out %s", ", ".join(f"{n} {r.replace('_', ' ')}" for r, n in dropped.most_common()))

    home = home or guess_home(keep)
    home_city = None
    if home:
        near = Counter(p.city for p in keep if p.has_gps and p.city and haversine_km(home, (p.lat, p.lon)) < opts.home_radius_km)
        home_city = near.most_common(1)[0][0] if near else None
    home_country = None
    if home:
        near = Counter(p.country for p in keep if p.has_gps and p.country and haversine_km(home, (p.lat, p.lon)) < opts.home_radius_km)
        home_country = near.most_common(1)[0][0] if near else None

    birthdays = {}
    try:
        for person in immich.people():
            if person.get("name") and person.get("birthDate"):
                birthdays[person["name"]] = date.fromisoformat(person["birthDate"][:10])
    except ImmichError as err:
        log.debug("Couldn't read people: %s", err)

    settings = DetectSettings(
        home=home,
        home_radius_km=opts.home_radius_km,
        min_photos_trip=opts.min_photos_trip,
        min_photos_holiday=opts.min_photos_holiday,
        min_photos_spike=opts.min_photos_spike,
        spike_factor=opts.spike_factor,
        country=country or None,
        subdivision=opts.holiday_subdivision or None,
    )
    events = detect_events(keep, settings, birthdays, today=today)
    new = [e for e in events if not state.overlaps(e.start, e.end)]
    log.info("Found %d events, %d of them new", len(events), len(new))
    # Newest first, so recent memories appear first; older ones follow on later runs.
    new.sort(key=lambda e: e.start, reverse=True)
    if opts.max_albums_per_run and len(new) > opts.max_albums_per_run:
        log.info("Making the newest %d this run; the rest follow on later runs", opts.max_albums_per_run)
        new = new[: opts.max_albums_per_run]

    cache = AnalysisCache(f"{data_dir}/analysis.sqlite")
    analyzer = Analyzer()
    exclude = set(opts.exclude_people_from_names)
    ai_state = {"enabled": opts.ai_names and ha.available}

    def ai(prompt: str):
        if not ai_state["enabled"]:
            return None
        text = ha.ai_generate(prompt, opts.ai_task_entity or None, opts.conversation_agent or None)
        if text is None:
            log.warning(
                "Home Assistant's AI didn't answer, so names come from templates this run. "
                "Set up an AI Task entity (Settings > System > General > AI suggestions) or a conversation agent."
            )
            ai_state["enabled"] = False
        return text

    used_names = {a.get("albumName") for a in immich.albums()}
    made = []
    for event in new:
        ids = [p.id for p in event.photos]
        event.tags = labels.scene_tags(ids)
        analyses = analyse_photos(event.photos, immich.preview, cache, analyzer)
        groups = make_groups(event.photos, analyses)
        scores = score_photos(groups, analyses, labels)
        chosen = select(groups, scores, opts.max_photos_per_album)
        cover = pick_cover(chosen, scores, analyses, labels)
        facts = gather_facts(event, exclude, home_country=None)
        name, how = name_event(event, facts, ai=ai, home=home_city)
        if name in used_names:
            name = f"{name} ({event.start:%b %Y})"
        used_names.add(name)
        description = f"{describe(event, facts)}\n\n{MARKER}"
        to_stack = [g for g in groups if len(g.photos) > 1]
        record = {
            "name": name,
            "named_by": how,
            "kind": event.kind,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "photos": len(chosen),
            "candidates": len(event.photos),
            "holiday": event.holiday,
            "person": event.person,
            **summarise_event(event.photos, chosen, scores),
        }
        if opts.dry_run:
            log.info(
                "[dry run] Would make %r (%s, %d of %d photos, %d stacks)",
                name, event.kind, len(chosen), len(event.photos), len(to_stack),
            )
            state.record(event.key, status="dry_run", **record)
            made.append(record)
            continue

        stacks = []
        if opts.create_stacks:
            for g in to_stack:
                try:
                    stacks.append(immich.create_stack([g.best.id] + [p.id for p in g.others]))
                except ImmichError as err:
                    log.warning("Couldn't stack %d similar photos: %s", len(g.photos), err)
        album = immich.create_album(name, description, [p.id for p in chosen])
        try:
            immich.set_album_cover(album["id"], cover.id)
        except ImmichError as err:
            log.debug("Couldn't set the cover photo: %s", err)
        state.record(event.key, status="created", album_id=album["id"], stacks=stacks, **record)
        state.save()
        made.append({**record, "album_id": album["id"], "stacks": len(stacks)})
        log.info(
            "Made %r: %d photos chosen from %d%s",
            name, len(chosen), len(event.photos), f", {len(stacks)} stacks" if stacks else "",
        )
    state.save()

    if opts.collections:
        update_collections(immich, state, home_country, ai, opts.dry_run, opts.min_memories_for_collection)
    return made
