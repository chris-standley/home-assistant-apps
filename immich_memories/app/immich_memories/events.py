"""Finding the moments worth a memory: trips, days out, holidays, birthdays and
days with a burst of photos."""

from __future__ import annotations

import bisect
import logging
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from dateutil.easter import easter
from dateutil.relativedelta import SU, relativedelta

from .immich import Photo

log = logging.getLogger(__name__)


@dataclass
class Event:
    kind: str  # trip, day_out, holiday, birthday, spike
    start: date
    end: date
    photos: list[Photo]
    holiday: str | None = None
    person: str | None = None  # birthday person's name
    age: int | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.start.isoformat()}:{self.end.isoformat()}"

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass
class DetectSettings:
    home: tuple[float, float] | None
    home_radius_km: float = 40
    min_photos_trip: int = 15
    min_photos_holiday: int = 10
    min_photos_spike: int = 25
    spike_factor: float = 3.0
    trip_gap_days: int = 2
    settle_days: int = 2
    country: str | None = None
    subdivision: str | None = None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def guess_home(photos: list[Photo]) -> tuple[float, float] | None:
    """The ~10 km grid cell with the most photos, for when Home Assistant has no location."""
    cells = Counter((round(p.lat * 10) / 10, round(p.lon * 10) / 10) for p in photos if p.has_gps)
    if not cells:
        return None
    return cells.most_common(1)[0][0]


# -- holidays --------------------------------------------------------------


def holiday_windows(years: set[int], country: str | None, subdivision: str | None) -> list[tuple[str, date, date]]:
    """(name, first day, last day) for the celebrations worth a memory."""
    out: list[tuple[str, date, date]] = []
    country = (country or "").upper() or None
    for y in sorted(years):
        e = easter(y)
        out += [
            ("Christmas", date(y, 12, 24), date(y, 12, 26)),
            ("New Year's Eve", date(y, 12, 31), date(y, 12, 31)),
            ("Easter", e - timedelta(days=2), e + timedelta(days=1)),
            ("Halloween", date(y, 10, 31), date(y, 10, 31)),
        ]
        if country in ("GB", "UK", "IE"):
            mothers = e - timedelta(days=21)  # Mothering Sunday
        else:
            mothers = date(y, 5, 1) + relativedelta(weekday=SU(+2))
        out.append(("Mother's Day", mothers, mothers))
        fathers = date(y, 6, 1) + relativedelta(weekday=SU(+3))
        out.append(("Father's Day", fathers, fathers))
        if country in ("GB", "UK"):
            out.append(("Bonfire Night", date(y, 11, 5), date(y, 11, 5)))
    covered = {d for _, s, e_ in out for d in _daterange(s, e_)}
    if country:
        try:
            import holidays

            public = holidays.country_holidays(
                "GB" if country == "UK" else country, subdiv=subdivision or None, years=sorted(years)
            )
            for d, name in sorted(public.items()):
                if d not in covered and "substitute" not in name.lower() and "observed" not in name.lower():
                    out.append((name, d, d))
        except Exception as err:  # unknown country code etc.
            log.warning("Couldn't load public holidays for %s: %s", country, err)
    return out


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# -- detection ---------------------------------------------------------------


def detect_events(
    photos: list[Photo],
    settings: DetectSettings,
    birthdays: dict[str, date] | None = None,
    today: date | None = None,
) -> list[Event]:
    """Find events in photos (already cleared of clutter)."""
    today = today or date.today()
    by_day: dict[date, list[Photo]] = defaultdict(list)
    for p in photos:
        by_day[p.day].append(p)
    if not by_day:
        return []
    days = sorted(by_day)
    home = settings.home or guess_home(photos)

    # 1. Trips and days out: runs of days spent away from home.
    def where(d: date) -> str:
        if home is None:
            return "unknown"
        geo = [haversine_km(home, (p.lat, p.lon)) for p in by_day[d] if p.has_gps]
        if not geo:
            return "unknown"
        return "away" if statistics.median(geo) > settings.home_radius_km else "home"

    status = {d: where(d) for d in days}
    events: list[Event] = []
    run: list[date] = []

    def close_run():
        if not run:
            return
        ph = [p for d in run for p in by_day[d]]
        if len(ph) >= settings.min_photos_trip:
            kind = "trip" if run[-1] > run[0] else "day_out"
            events.append(Event(kind, run[0], run[-1], sorted(ph, key=lambda p: p.local_dt)))

    pending_unknown: list[date] = []
    for d in days:
        s = status[d]
        if s == "away":
            if run and (d - run[-1]).days <= settings.trip_gap_days + 1:
                run.extend(pending_unknown)
                run.append(d)
            else:
                close_run()
                run = [d]
            pending_unknown = []
        elif s == "unknown" and run:
            pending_unknown.append(d)
        else:
            close_run()
            run, pending_unknown = [], []
    close_run()

    used: set[date] = {d for e in events for d in _daterange(e.start, e.end)}

    # 2. Holidays at home (a trip over Christmas keeps the trip, and notes the holiday).
    years = {d.year for d in days}
    for name, start, end in holiday_windows(years, settings.country, settings.subdivision):
        window = list(_daterange(start, end))
        for e in events:
            if e.holiday is None and any(e.start <= d <= e.end for d in window):
                e.holiday = name
        free = [d for d in window if d not in used and d in by_day]
        ph = [p for d in free for p in by_day[d]]
        if len(ph) >= settings.min_photos_holiday:
            events.append(Event("holiday", free[0], free[-1], sorted(ph, key=lambda p: p.local_dt), holiday=name))
            used.update(free)

    # 3. Birthdays of people Immich knows, when they're in the photos that day.
    for name, born in (birthdays or {}).items():
        for y in years:
            try:
                d = born.replace(year=y)
            except ValueError:  # 29 February
                d = date(y, 3, 1)
            if d in used or d not in by_day or y <= born.year:
                continue
            ph = by_day[d]
            with_them = [p for p in ph if any(pp.name == name for pp in p.people)]
            if len(with_them) >= 3 and len(ph) >= settings.min_photos_holiday:
                events.append(Event("birthday", d, d, sorted(ph, key=lambda p: p.local_dt), person=name, age=y - born.year))
                used.add(d)

    # 4. Spikes: days with far more photos than usual.
    counts = [len(by_day[d]) for d in days]
    ordinals = [d.toordinal() for d in days]
    spike_days = []
    for i, d in enumerate(days):
        if d in used:
            continue
        lo = bisect.bisect_left(ordinals, ordinals[i] - 60)
        hi = bisect.bisect_right(ordinals, ordinals[i] + 60)
        nearby = counts[lo:i] + counts[i + 1 : hi]
        baseline = statistics.median(nearby) if nearby else 0
        if counts[i] >= max(settings.min_photos_spike, settings.spike_factor * baseline):
            spike_days.append(d)
    group: list[date] = []
    for d in spike_days + [None]:
        if d is not None and group and (d - group[-1]).days == 1 and len(group) < 3:
            group.append(d)
            continue
        if group:
            ph = [p for g in group for p in by_day[g]]
            events.append(Event("spike", group[0], group[-1], sorted(ph, key=lambda p: p.local_dt)))
        group = [d] if d is not None else []

    # Leave events that may still be happening until they've settled.
    cutoff = today - timedelta(days=settings.settle_days)
    settled = [e for e in events if e.end < cutoff]
    return sorted(settled, key=lambda e: e.start)
