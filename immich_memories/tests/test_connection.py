"""Reaching Immich: hostnames Home Assistant can't look up, certificates, fallbacks."""

from __future__ import annotations

import ssl
import subprocess

import pytest

from fake_immich_server import API_KEY, serve
from immich_memories import immich as immich_module
from immich_memories.runner import Options, connect
from test_memories import FakeHA, FakeImmich

HOST = "immich.example.test"  # .test never resolves


@pytest.fixture
def server():
    srv = serve(FakeImmich([]))
    yield srv
    srv.shutdown()


@pytest.fixture(autouse=True)
def unpin(monkeypatch):
    # No proxies: the app talks to Immich directly, as it does inside Home Assistant.
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    yield
    immich_module._pinned.clear()


def test_unresolvable_hostname_explains_what_to_do(server):
    opts = Options(immich_url=f"http://{HOST}:{server.server_port}", immich_api_key=API_KEY)
    with pytest.raises(SystemExit) as err:
        connect(opts, FakeHA())
    assert "couldn't be looked up" in str(err.value)
    assert "Immich IP address" in str(err.value)


def test_ip_address_option_connects_using_the_hostname(server):
    opts = Options(immich_url=f"http://{HOST}:{server.server_port}", immich_ip="127.0.0.1", immich_api_key=API_KEY)
    client = connect(opts, FakeHA())
    assert client.base == f"http://{HOST}:{server.server_port}/api"


def test_falls_back_to_the_immich_app_when_the_url_fails(server):
    ha = FakeHA()
    ha.discovered = [f"http://127.0.0.1:{server.server_port}"]
    opts = Options(immich_url=f"http://{HOST}:{server.server_port}", immich_api_key=API_KEY)
    client = connect(opts, ha)
    assert client.base == f"http://127.0.0.1:{server.server_port}/api"


def test_url_without_scheme():
    assert immich_module.Immich("192.168.1.5:2283", "k").base == "http://192.168.1.5:2283/api"


@pytest.fixture
def https_server(tmp_path):
    """The fake Immich over HTTPS with a self-signed certificate for HOST only."""
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    try:
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", f"/CN={HOST}",
             "-addext", f"subjectAltName=DNS:{HOST}", "-keyout", str(key), "-out", str(cert)],
            check=True, capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("openssl not available")
    srv = serve(FakeImmich([]))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    yield srv, cert
    srv.shutdown()


def test_certificate_for_hostname_fails_by_ip_and_skipping_checks_works(https_server):
    srv, _ = https_server
    url = f"https://127.0.0.1:{srv.server_port}"
    with pytest.raises(SystemExit) as err:
        connect(Options(immich_url=url, immich_api_key=API_KEY), FakeHA())
    assert "certificate" in str(err.value)
    client = connect(Options(immich_url=url, immich_api_key=API_KEY, verify_ssl=False), FakeHA())
    assert client.version() == "3.3.0"


def test_hostname_plus_ip_keeps_certificate_checks(https_server, monkeypatch):
    srv, cert = https_server
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(cert))  # trust our test CA, as a real one would be
    opts = Options(immich_url=f"https://{HOST}:{srv.server_port}", immich_ip="127.0.0.1", immich_api_key=API_KEY)
    client = connect(opts, FakeHA())
    assert client.version() == "3.3.0"
