"""Collections that gather recurring memories and grow each year."""

from __future__ import annotations

from datetime import date, datetime

from immich_memories.runner import Options, run
from test_memories import EMMA, JACK, FakeHA, FakeImmich, asset, every


def christmas(year):
    return every(datetime(year, 12, 25, 9), 14, minutes=25, place="leeds", people=[EMMA, JACK])


def library():
    lib = []
    for year in (2022, 2023):
        lib += christmas(year)
    # Two Norway holidays.
    lib += every(datetime(2022, 7, 1, 9), 10, minutes=40, place="bergen") + every(datetime(2022, 7, 2, 9), 10, minutes=40, place="bergen")
    lib += every(datetime(2023, 2, 10, 9), 10, minutes=40, place="tromso") + every(datetime(2023, 2, 11, 9), 10, minutes=40, place="tromso")
    # Three visits to the Lake District, staying in different towns.
    lib += every(datetime(2022, 5, 7, 10), 18, minutes=12, place="ambleside", people=[EMMA])
    lib += every(datetime(2023, 9, 2, 10), 18, minutes=12, place="keswick", people=[EMMA])
    lib += every(datetime(2023, 10, 14, 10), 18, minutes=12, place="ambleside")
    return lib


def album(immich, name):
    return next(a for a in immich.albums_made if a["name"] == name)


def test_collections_are_made_and_topped_up(tmp_path):
    lib = library()
    immich = FakeImmich(lib)
    opts = Options(immich_api_key="x")
    def ai(prompt):
        if "same area" in prompt:
            return "Trips to the Lake District" if "Keswick" in prompt else None
        return prompt.split("- Suggested title: ")[1].splitlines()[0]  # keep the template name

    ha = FakeHA(ai_reply=ai)
    run(opts, ha, data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    names = {a["name"] for a in immich.albums_made}
    assert {"Christmas through the years", "Holidays in Norway", "Trips to the Lake District"} <= names

    xmas = album(immich, "Christmas through the years")
    ids_2022 = {a["id"] for a in lib if a["localDateTime"].startswith("2022-12-25")}
    ids_2023 = {a["id"] for a in lib if a["localDateTime"].startswith("2023-12-25")}
    assert set(xmas["assets"]) & ids_2022 and set(xmas["assets"]) & ids_2023
    assert "Made by Immich Memories" in xmas["description"]

    # You take a photo out of the collection; it stays out.
    removed = xmas["assets"][0]
    xmas["assets"] = xmas["assets"][1:]

    # A year later, Christmas 2024 joins the same album.
    immich.assets = lib + christmas(2024)
    run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=immich)
    xmas = album(immich, "Christmas through the years")
    ids_2024 = {a["id"] for a in immich.assets if a["localDateTime"].startswith("2024-12-25")}
    assert set(xmas["assets"]) & ids_2024
    assert removed not in xmas["assets"]
    assert sum(a["name"] == "Christmas through the years" for a in immich.albums_made) == 1


def test_one_of_a_kind_makes_no_collection(tmp_path):
    immich = FakeImmich(christmas(2023))
    run(Options(immich_api_key="x"), FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    assert [a["name"] for a in immich.albums_made] == ["Christmas 2023"]


def test_deleted_collection_stays_deleted(tmp_path):
    immich = FakeImmich(library())
    opts = Options(immich_api_key="x")
    run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    immich.delete_album(album(immich, "Holidays in Norway")["id"])
    run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    assert "Holidays in Norway" not in {a["name"] for a in immich.albums_made}


def test_collections_can_be_turned_off(tmp_path):
    immich = FakeImmich(library())
    run(Options(immich_api_key="x", collections=False), FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    assert not any("through the years" in a["name"] for a in immich.albums_made)


def test_place_fallback_name_without_ai(tmp_path):
    immich = FakeImmich(library())
    run(Options(immich_api_key="x"), FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=immich)
    assert "Trips to Ambleside" in {a["name"] for a in immich.albums_made}
