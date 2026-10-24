"""Game maps: cities, routes, destination tickets and scoring rules.

Each map is a JSON file in maps/. Adding a map is a matter of dropping in
another file with the same shape (see usa.json); nothing else needs to change.
Routes are listed once per lane, so a double route appears twice. A route can
carry a fifth element, "tunnel" or "ferry", which only affects how it's drawn.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

MAPS_DIR = Path(__file__).parent / "maps"


@dataclass(frozen=True)
class Route:
    id: str
    a: str
    b: str
    length: int
    color: str
    kind: str = ""  # "", "tunnel" or "ferry"
    lane: int = 0  # 0 for a single route; 1 and 2 for the lanes of a double

    def other(self, city: str) -> str:
        return self.b if city == self.a else self.a


@dataclass(frozen=True)
class Ticket:
    id: str
    a: str
    b: str
    points: int
    long: bool = False


@dataclass
class GameMap:
    id: str
    name: str
    trains_per_player: int
    route_points: dict[int, int]
    longest_route_bonus: int
    longest_route_name: str
    player_colors: list[str]
    double_routes_min_players: int
    size: tuple[int, int]
    cities: dict[str, tuple[int, int]]
    routes: dict[str, Route]
    tickets: dict[str, Ticket]
    stations: int = 0
    station_points: int = 0
    aliases: dict[str, str] = field(default_factory=dict)

    # -- lookups ------------------------------------------------------------

    def city(self, name: str) -> str | None:
        """The map's spelling of a city name, forgiving case, accents and aliases."""
        if not name:
            return None
        key = _norm(name)
        for city in self.cities:
            if _norm(city) == key:
                return city
        for alias, city in self.aliases.items():
            if _norm(alias) == key:
                return city
        return None

    def find_ticket(self, a: str, b: str) -> Ticket | None:
        ca, cb = self.city(a), self.city(b)
        if not ca or not cb:
            return None
        for t in self.tickets.values():
            if {t.a, t.b} == {ca, cb}:
                return t
        return None

    def routes_between(self, a: str, b: str) -> list[Route]:
        return [r for r in self.routes.values() if {r.a, r.b} == {a, b}]

    def points_for(self, length: int) -> int:
        return self.route_points.get(length, 0)

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "trains_per_player": self.trains_per_player,
            "route_points": {str(k): v for k, v in self.route_points.items()},
            "longest_route_bonus": self.longest_route_bonus,
            "longest_route_name": self.longest_route_name,
            "player_colors": self.player_colors,
            "double_routes_min_players": self.double_routes_min_players,
            "stations": self.stations,
            "station_points": self.station_points,
            "size": list(self.size),
            "cities": {k: list(v) for k, v in self.cities.items()},
            "routes": [
                {
                    "id": r.id,
                    "a": r.a,
                    "b": r.b,
                    "length": r.length,
                    "color": r.color,
                    "kind": r.kind,
                    "lane": r.lane,
                }
                for r in self.routes.values()
            ],
            "tickets": [
                {"id": t.id, "a": t.a, "b": t.b, "points": t.points, "long": t.long} for t in self.tickets.values()
            ],
        }


def _norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", "and")
    text = re.sub(r"\bste?\b\.?", "saint", text)  # St. / Ste. -> saint
    return re.sub(r"[^a-z0-9]", "", text)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip("_")


def load_map(path: Path) -> GameMap:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cities = {name: (int(xy[0]), int(xy[1])) for name, xy in raw["cities"].items()}

    pairs: dict[tuple[str, str], int] = {}
    for a, b, *_ in raw["routes"]:
        key = tuple(sorted((a, b)))
        pairs[key] = pairs.get(key, 0) + 1

    routes: dict[str, Route] = {}
    seen: dict[tuple[str, str], int] = {}
    for entry in raw["routes"]:
        a, b, length, color = entry[:4]
        kind = entry[4] if len(entry) > 4 else ""
        if a not in cities or b not in cities:
            raise ValueError(f"{path.name}: route {a}-{b} names an unknown city")
        key = tuple(sorted((a, b)))
        seen[key] = seen.get(key, 0) + 1
        lane = seen[key] if pairs[key] > 1 else 0
        rid = f"{_slug(a)}-{_slug(b)}" + (f"-{lane}" if lane else "")
        routes[rid] = Route(rid, a, b, int(length), color, kind, lane)

    tickets: dict[str, Ticket] = {}
    for entry in raw["tickets"]:
        a, b, points = entry[:3]
        if a not in cities or b not in cities:
            raise ValueError(f"{path.name}: ticket {a}-{b} names an unknown city")
        tid = f"{_slug(a)}-{_slug(b)}"
        tickets[tid] = Ticket(tid, a, b, int(points), len(entry) > 3 and entry[3] == "long")

    return GameMap(
        id=raw["id"],
        name=raw["name"],
        trains_per_player=int(raw.get("trains_per_player", 45)),
        route_points={int(k): int(v) for k, v in raw["route_points"].items()},
        longest_route_bonus=int(raw.get("longest_route_bonus", 10)),
        longest_route_name=raw.get("longest_route_name", "Longest route"),
        player_colors=list(raw.get("player_colors", ["red", "blue", "green", "yellow", "black"])),
        double_routes_min_players=int(raw.get("double_routes_min_players", 4)),
        size=tuple(raw.get("size", [1000, 650])),
        cities=cities,
        routes=routes,
        tickets=tickets,
        stations=int(raw.get("stations", 0)),
        station_points=int(raw.get("station_points", 0)),
        aliases=dict(raw.get("aliases", {})),
    )


_cache: dict[str, GameMap] = {}


def all_maps() -> dict[str, GameMap]:
    if not _cache:
        for path in sorted(MAPS_DIR.glob("*.json")):
            m = load_map(path)
            _cache[m.id] = m
    return _cache


def get_map(map_id: str) -> GameMap:
    maps = all_maps()
    if map_id not in maps:
        raise KeyError(f"Unknown map {map_id!r}")
    return maps[map_id]
