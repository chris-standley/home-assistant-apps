import json

from ticket_to_ride import vision
from ticket_to_ride.maps import get_map


def test_board_instructions_list_every_route():
    m = get_map("usa")
    text = vision.board_instructions(m, ["red", "blue"])
    for r in m.routes.values():
        assert f"{r.id}:" in text
    assert "stations" not in text
    assert "stations" in vision.board_instructions(get_map("europe"), ["red"])


def test_parse_board_tolerates_fences_and_bad_entries():
    m = get_map("usa")
    reply = (
        "Here you go:\n```json\n"
        + json.dumps(
            {
                "routes": [
                    {"id": "denver-santa_fe", "player": "Red"},
                    {"id": "boston-new_york-1", "player": "grey"},  # not a player colour
                    {"id": "made-up", "player": "blue"},
                    {"id": "seattle-helena", "player": "blue"},
                ]
            }
        )
        + "\n```"
    )
    out = vision.parse_board(m, ["red", "blue"], reply)
    assert out["routes"] == {"denver-santa_fe": "red", "seattle-helena": "blue"}
    assert out["skipped"] == 2


def test_parse_board_stations():
    m = get_map("europe")
    reply = json.dumps(
        {
            "routes": [],
            "stations": [
                {"city": "Vienna", "player": "red"},
                {"city": "Roma", "player": "red"},
                {"city": "Berlin", "player": "red"},
                {"city": "Paris", "player": "red"},  # a fourth is dropped
                {"city": "Atlantis", "player": "blue"},
            ],
        }
    )
    out = vision.parse_board(m, ["red", "blue"], reply)
    assert out["stations"] == {"red": ["Wien", "Roma", "Berlin"], "blue": []}


def test_parse_tickets_matches_known_and_keeps_unknown():
    m = get_map("usa")
    reply = json.dumps(
        {
            "tickets": [
                {"id": "denver-el_paso", "a": "Denver", "b": "El Paso", "points": 4},
                {"id": "", "a": "St. Louis", "b": "Chicago", "points": 3},  # not in the base deck
                {"id": "", "a": "Houston", "b": "Kansas City", "points": 5},  # matched by cities
                {"id": "denver-el_paso"},  # duplicate
            ]
        }
    )
    out = vision.parse_tickets(m, reply)
    assert [(t["a"], t["b"], t["points"]) for t in out] == [
        ("Denver", "El Paso", 4),
        ("Saint Louis", "Chicago", 3),
        ("Kansas City", "Houston", 5),
    ]
