"""Friendly album names from where, when and who.

A template name is always built from Immich's own data (places from reverse
geocoding, people from face recognition, dates, scene labels). When enabled,
Home Assistant's AI is then asked to polish it, given the same facts; its
answer is used only if it looks like a sensible title.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from .events import Event

log = logging.getLogger(__name__)

REGIONS = {
    "Mediterranean": {
        "Spain", "France", "Italy", "Greece", "Croatia", "Malta", "Cyprus", "Turkey", "Türkiye", "Monaco",
        "Montenegro", "Slovenia", "Albania", "Tunisia", "Gibraltar", "Israel", "Lebanon",
    },
    "Caribbean": {
        "Jamaica", "Bahamas", "The Bahamas", "Barbados", "Saint Lucia", "Antigua and Barbuda", "Aruba", "Curaçao",
        "Dominican Republic", "Puerto Rico", "Cayman Islands", "Grenada", "Saint Kitts and Nevis",
        "U.S. Virgin Islands", "British Virgin Islands", "Sint Maarten", "Saint Martin", "Bermuda", "Cuba",
        "Turks and Caicos Islands", "Dominica", "Saint Vincent and the Grenadines", "Trinidad and Tobago",
        "Guadeloupe", "Martinique",
    },
    "Scandinavia": {"Norway", "Sweden", "Denmark", "Finland", "Iceland"},
    "Baltic": {"Estonia", "Latvia", "Lithuania", "Finland", "Sweden", "Denmark", "Germany", "Poland", "Russia"},
    "Benelux": {"Belgium", "Netherlands", "The Netherlands", "Luxembourg"},
    "Alps": {"Switzerland", "Austria", "Liechtenstein", "France", "Italy", "Germany"},
    "Balkans": {
        "Croatia", "Slovenia", "Bosnia and Herzegovina", "Serbia", "Montenegro", "North Macedonia", "Albania",
        "Kosovo", "Bulgaria",
    },
    "Southeast Asia": {"Thailand", "Vietnam", "Cambodia", "Laos", "Malaysia", "Singapore", "Indonesia", "Philippines"},
    "Central America": {"Mexico", "Belize", "Guatemala", "Costa Rica", "Panama", "Nicaragua", "Honduras", "El Salvador"},
    "Europe": {
        "United Kingdom", "Ireland", "France", "Spain", "Portugal", "Italy", "Germany", "Netherlands",
        "The Netherlands", "Belgium", "Luxembourg", "Switzerland", "Austria", "Denmark", "Norway", "Sweden",
        "Finland", "Iceland", "Poland", "Czechia", "Czech Republic", "Slovakia", "Hungary", "Slovenia", "Croatia",
        "Greece", "Malta", "Cyprus", "Estonia", "Latvia", "Lithuania", "Romania", "Bulgaria", "Monaco",
        "Montenegro", "Albania", "Serbia", "Bosnia and Herzegovina", "North Macedonia", "Liechtenstein",
        "Andorra", "San Marino", "Vatican City", "Gibraltar",
    },
}

MONTHS = "January February March April May June July August September October November December".split()


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def join_names(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " & " + names[-1]


@dataclass
class Facts:
    place: str | None
    cities: list[str]
    regions: list[str]  # states/counties
    countries: list[str]
    people: list[str]
    itinerary: list[str]  # one line per day for trips

    def summary(self) -> str:
        return ", ".join(self.cities[:4] or self.regions[:3] or self.countries[:3])


def _dominant(counter: Counter, share: float) -> str | None:
    total = sum(counter.values())
    if not total:
        return None
    value, n = counter.most_common(1)[0]
    return value if n / total >= share else None


def gather_facts(event: Event, exclude_people: set[str], home_country: str | None = None) -> Facts:
    photos = event.photos
    cities = Counter(p.city for p in photos if p.city)
    states = Counter(p.state for p in photos if p.state)
    countries = Counter(p.country for p in photos if p.country)

    place = None
    if countries:
        country = _dominant(countries, 0.8)
        if country:
            place = _dominant(cities, 0.6) or _dominant(states, 0.6) or country
            # "Trip to England" reads oddly for an English family; prefer the city.
            if place == home_country and cities:
                place = cities.most_common(1)[0][0]
        else:
            main = [c for c, n in countries.items() if n / sum(countries.values()) >= 0.1]
            if len(main) == 2:
                place = " & ".join(sorted(main))
            else:
                for region, members in REGIONS.items():
                    if set(main) <= members:
                        place = region
                        break
                place = place or countries.most_common(1)[0][0]

    tally = Counter(pp.name for p in photos for pp in p.named_people if pp.name not in exclude_people)
    with_people = sum(1 for p in photos if p.named_people) or 1
    people = [n for n, c in tally.most_common(4) if c >= 3 and c / with_people >= 0.25]
    if len(people) > 3:
        people = []  # a crowd; "with the family" is for the AI to decide

    itinerary = []
    if event.kind == "trip":
        by_day: dict = {}
        for p in photos:
            by_day.setdefault(p.day, Counter())
            label = p.city or p.state or p.country
            if label:
                by_day[p.day][label] += 1
        for day, c in sorted(by_day.items()):
            where = ", ".join(x for x, _ in c.most_common(2)) or "unknown"
            itinerary.append(f"{day:%a %d %b}: {where}")

    return Facts(
        place=place,
        cities=[c for c, _ in cities.most_common(6)],
        regions=[c for c, _ in states.most_common(3)],
        countries=[c for c, _ in countries.most_common(4)],
        people=people,
        itinerary=itinerary,
    )


def year_label(event: Event) -> str:
    if event.end.year != event.start.year:
        return f"{event.start.year}–{str(event.end.year)[-2:]}"
    return str(event.start.year)


def template_name(event: Event, facts: Facts) -> str:
    year = year_label(event)
    place = facts.place
    tags = event.tags
    who = join_names(facts.people)
    with_who = f" with {who}" if who else ""
    month = f"{MONTHS[event.start.month - 1]} {event.start.year}"

    if event.kind == "birthday" and event.person:
        if event.age and event.age <= 18:
            return f"{event.person}'s {ordinal(event.age)} birthday"
        return f"{event.person}'s birthday {year}"

    if event.kind == "holiday" and event.holiday:
        return f"{event.holiday} {year}"

    if event.kind == "trip":
        if not place:
            return f"Trip, {month}"
        if event.holiday in ("Christmas", "New Year's Eve", "Easter"):
            return f"{event.holiday} in {place} {year}"
        if "cruise" in tags:
            return f"{place} cruise {year}"
        if "snow" in tags:
            return f"Ski trip to {place} {year}"
        if "beach" in tags:
            return f"Beach holiday in {place} {year}"
        if event.days <= 3 and event.start.weekday() >= 4:
            return f"Weekend in {place}{with_who}"
        return f"{place} trip {year}" if place in REGIONS else f"Trip to {place} {year}"

    if event.kind == "day_out":
        at = f" in {place}" if place else ""
        for tag, phrase in (
            ("hiking", f"Walk{at}"),
            ("beach", f"Beach day{' at ' + place if place else ''}"),
            ("theme_park", "Theme park day"),
            ("zoo", "Day at the zoo"),
            ("snow", f"Snow day{at}"),
            ("lake", f"Day by the lake{at}"),
            ("concert", "Concert"),
            ("wedding", "Wedding"),
        ):
            if tag in tags:
                return f"{phrase}{with_who}"
        return f"Day out{at}{with_who}"

    # A burst of photos on an ordinary day.
    for tag, phrase in (
        ("wedding", "Wedding"),
        ("party", "Party"),
        ("concert", "Concert"),
        ("christmas", "Christmas"),
        ("snow", "Snow day"),
        ("beach", "Beach day"),
        ("hiking", "Walk"),
        ("garden", "In the garden"),
        ("camping", "Camping"),
    ):
        if tag in tags:
            return f"{phrase}{with_who}, {month}"
    if who:
        return f"Day with {who}, {month}"
    city = facts.cities[0] if facts.cities else None
    return f"Day in {city}, {month}" if city else f"{event.start:%-d} {month}"


AI_PROMPT = """You write short, warm titles for photo memories, like the memories in Apple Photos.

Examples of the style: "Mediterranean cruise 2024", "Walk in the Lake District with Emma", "Christmas 2023", \
"Weekend in Paris", "Beach day at Woolacombe".

Write one title for this memory using only these facts. Use a well-known name for the area if the towns \
clearly belong to one (for example a national park, island or coast). Mention people only if they are listed. \
Don't invent activities that the facts don't suggest. Only call it someone's birthday if "Birthday of" is \
listed below; a party or a cake on another day is not a birthday. Keep it under 45 characters. Reply with the title only, \
no quotes or punctuation at the end.

Facts:
{facts}
"""


def ai_facts(event: Event, facts: Facts, template: str, home: str | None) -> str:
    lines = [
        f"- Kind of memory: {event.kind.replace('_', ' ')}",
        f"- Dates: {event.start:%a %d %b %Y}" + (f" to {event.end:%a %d %b %Y} ({event.days} days)" if event.days > 1 else ""),
        f"- Number of photos: {len(event.photos)}",
    ]
    if home:
        lines.append(f"- Home is near: {home}")
    if facts.place:
        lines.append(f"- Main place: {facts.place}")
    if facts.cities:
        lines.append(f"- Towns and cities: {', '.join(facts.cities)}")
    if facts.regions:
        lines.append(f"- Regions: {', '.join(facts.regions)}")
    if facts.countries:
        lines.append(f"- Countries: {', '.join(facts.countries)}")
    if facts.people:
        lines.append(f"- People in many of the photos: {', '.join(facts.people)}")
    if event.holiday:
        lines.append(f"- Holiday: {event.holiday}")
    if event.kind == "birthday" and event.person:
        lines.append(f"- Birthday of: {event.person}" + (f", turning {event.age}" if event.age else ""))
    if event.tags:
        lines.append(f"- What the photos show: {', '.join(t.replace('_', ' ') for t in event.tags)}")
    if facts.itinerary:
        lines.append("- Day by day:\n" + "\n".join(f"    {x}" for x in facts.itinerary[:21]))
    lines.append(f"- Suggested title: {template}")
    return "\n".join(lines)


def _wrong_birthday(title: str, event: Event) -> bool:
    """An AI title calling this someone's birthday when it isn't."""
    if not re.search(r"birthday", title, re.IGNORECASE):
        return False
    return not (event.kind == "birthday" and event.person and event.person.lower() in title.lower())


def clean_ai_title(text: str | None) -> str | None:
    if not text:
        return None
    line = next((l for l in text.strip().splitlines() if l.strip()), "")
    line = re.sub(r"^(title|album|name)\s*:\s*", "", line.strip(), flags=re.IGNORECASE)
    line = line.strip().strip("*_#`\"'“”‘’ ").rstrip(".!")
    if not 3 <= len(line) <= 60:
        return None
    if re.search(r"\b(sorry|cannot|can't|unable|I'm|as an ai)\b", line, re.IGNORECASE):
        return None
    return line


def name_event(event: Event, facts: Facts, ai=None, home: str | None = None) -> tuple[str, str]:
    """(name, how it was made: "ai" or "template")."""
    template = template_name(event, facts)
    if ai is not None:
        title = clean_ai_title(ai(AI_PROMPT.format(facts=ai_facts(event, facts, template, home))))
        if title and _wrong_birthday(title, event):
            log.info("Ignoring AI title %r: it isn't anyone's birthday that day", title)
            title = None
        if title:
            return title, "ai"
    return template, "template"


def describe(event: Event, facts: Facts) -> str:
    if event.days == 1:
        when = f"{event.start:%-d %B %Y}"
    elif event.start.year == event.end.year:
        when = f"{event.start:%-d %b} – {event.end:%-d %b %Y}"
    else:
        when = f"{event.start:%-d %b %Y} – {event.end:%-d %b %Y}"
    where = facts.summary()
    return " · ".join(x for x in (when, where) if x)
