"""Reading the board and destination tickets from photos.

The AI is given the full list of routes (or tickets) on the map, each with an
id, and asked which ones it can see. Tying its answer to known ids keeps the
result usable even when it misreads a city name, and anything it gets wrong is
fixed on the page before scoring.
"""

from __future__ import annotations

import json
import re

from .maps import GameMap


def board_instructions(game_map: GameMap, colors: list[str]) -> str:
    lines = [
        f"This is a photo of a finished game of the board game Ticket to Ride, {game_map.name} map.",
        f"The players' plastic train cars are these colours: {', '.join(colors)}.",
        "",
        "Every route on the map is listed below as: id: city - city, number of spaces, colour printed on the board"
        " (gray routes can be claimed with any colour). Double routes are two parallel tracks with separate ids.",
        "",
        "For every route that has train cars sitting on its spaces, say which player colour the train cars are."
        " Only include a route when its spaces are covered by train cars; the printed colour of an empty route is"
        " not a player. For a double route, say which of the two tracks is covered by comparing the printed colours.",
    ]
    if game_map.stations:
        lines.append(
            "Players may also have placed small train station pieces on cities. List each station's city and colour."
        )
    lines += [
        "",
        "Answer with JSON only, no other text, in this shape:",
        '{"routes": [{"id": "<route id>", "player": "<colour>"}]'
        + (', "stations": [{"city": "<city>", "player": "<colour>"}]' if game_map.stations else "")
        + "}",
        "",
        "Routes:",
    ]
    for r in game_map.routes.values():
        extra = f", {r.kind}" if r.kind else ""
        lines.append(f"{r.id}: {r.a} - {r.b}, {r.length}, {r.color}{extra}")
    return "\n".join(lines)


def tickets_instructions(game_map: GameMap) -> str:
    lines = [
        f"This is a photo of one player's destination ticket cards from the board game Ticket to Ride,"
        f" {game_map.name} map. Each card names two cities and a point value.",
        "",
        "List every ticket card you can see. Use the id from the list below when the card matches one; otherwise"
        " give the two city names and the points printed on the card.",
        "",
        "Answer with JSON only, no other text, in this shape:",
        '{"tickets": [{"id": "<ticket id or empty>", "a": "<city>", "b": "<city>", "points": <number>}]}',
        "",
        "Known tickets:",
    ]
    for t in game_map.tickets.values():
        lines.append(f"{t.id}: {t.a} - {t.b}, {t.points}")
    return "\n".join(lines)


def _json_from(text: str) -> dict:
    """Pull the first JSON object out of an AI reply (tolerates code fences and chatter)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON in the AI's answer")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unfinished JSON in the AI's answer")


def _color(value: str, colors: list[str]) -> str | None:
    value = (value or "").strip().lower()
    synonyms = {"grey": "gray", "purple": "pink", "violet": "pink"}
    value = synonyms.get(value, value)
    return value if value in colors else None


def parse_board(game_map: GameMap, colors: list[str], text: str) -> dict:
    data = _json_from(text)
    routes: dict[str, str] = {}
    unknown = 0
    for item in data.get("routes") or []:
        if not isinstance(item, dict):
            continue
        color = _color(str(item.get("player", "")), colors)
        rid = str(item.get("id", "")).strip()
        if rid not in game_map.routes or not color:
            unknown += 1
            continue
        routes[rid] = color
    stations: dict[str, list[str]] = {c: [] for c in colors}
    for item in data.get("stations") or []:
        if not isinstance(item, dict):
            continue
        city = game_map.city(str(item.get("city", "")))
        color = _color(str(item.get("player", "")), colors)
        if city and color and len(stations[color]) < game_map.stations and city not in stations[color]:
            stations[color].append(city)
    return {"routes": routes, "stations": stations if game_map.stations else {}, "skipped": unknown}


def parse_tickets(game_map: GameMap, text: str) -> list[dict]:
    data = _json_from(text)
    out: list[dict] = []
    seen: set[str] = set()
    for item in data.get("tickets") or []:
        if not isinstance(item, dict):
            continue
        ticket = game_map.tickets.get(str(item.get("id", "")).strip())
        if ticket is None:
            ticket = game_map.find_ticket(str(item.get("a", "")), str(item.get("b", "")))
        if ticket is not None:
            if ticket.id in seen:
                continue
            seen.add(ticket.id)
            out.append({"a": ticket.a, "b": ticket.b, "points": ticket.points, "id": ticket.id})
            continue
        a, b = game_map.city(str(item.get("a", ""))), game_map.city(str(item.get("b", "")))
        try:
            points = int(item.get("points") or 0)
        except (TypeError, ValueError):
            points = 0
        if a and b and a != b:
            out.append({"a": a, "b": b, "points": points, "id": ""})
    return out
