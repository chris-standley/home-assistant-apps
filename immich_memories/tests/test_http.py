"""The real Immich client against a fake Immich server, over HTTP."""

from __future__ import annotations

from datetime import date

from fake_immich_server import API_KEY, serve
from immich_memories.immich import Immich
from immich_memories.runner import Options, connect, run
from test_memories import FakeHA, FakeImmich, build_library


def test_run_over_http(tmp_path, monkeypatch):
    monkeypatch.setattr("immich_memories.immich.PAGE_SIZE", 50)  # exercise cursor paging
    lib, receipts = build_library()
    fake = FakeImmich(lib, labels={"receipt": receipts})
    server = serve(fake)
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        opts = Options(immich_url=url, immich_api_key=API_KEY)
        client = connect(opts, FakeHA())
        assert len(client.all_photos()) == len(lib)
        made = run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=client)
        assert {m["name"] for m in made} >= {"Christmas 2024", "Jack's 5th birthday"}
        assert len(fake.albums_made) == len(made)
        assert len(fake.covers) == len(made)
    finally:
        server.shutdown()


def test_bad_api_key_is_reported(monkeypatch):
    fake = FakeImmich([])
    server = serve(fake)
    try:
        opts = Options(immich_url=f"http://127.0.0.1:{server.server_port}", immich_api_key="wrong")
        try:
            connect(opts, FakeHA())
        except SystemExit as err:
            assert "rejected the API key" in str(err)
        else:
            raise AssertionError("expected a clear error")
    finally:
        server.shutdown()


def test_url_gets_api_suffix():
    assert Immich("http://immich:2283", "k").base == "http://immich:2283/api"
    assert Immich("http://immich:2283/api/", "k").base == "http://immich:2283/api"


def test_collections_over_http(tmp_path):
    from test_collections import christmas, library

    fake = FakeImmich(library())
    server = serve(fake)
    try:
        opts = Options(immich_url=f"http://127.0.0.1:{server.server_port}", immich_api_key=API_KEY)
        client = connect(opts, FakeHA())
        run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2024, 1, 10), immich=client)
        before = len(next(a for a in fake.albums_made if a["name"] == "Christmas through the years")["assets"])
        fake.assets = fake.assets + christmas(2024)
        run(opts, FakeHA(), data_dir=str(tmp_path), today=date(2025, 1, 10), immich=client)
        after = len(next(a for a in fake.albums_made if a["name"] == "Christmas through the years")["assets"])
        assert after > before
    finally:
        server.shutdown()
