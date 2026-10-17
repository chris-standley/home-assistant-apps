"""A small client for the parts of the Immich API this app uses.

Written against Immich v1.120+ through v3.x. Search pagination switched from
`page`/`nextPage` to `cursor`/`nextCursor` in v3.2, so both are followed.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

import requests
import urllib3

log = logging.getLogger(__name__)

PAGE_SIZE = 1000


class ImmichError(RuntimeError):
    pass


@dataclass
class Person:
    id: str
    name: str


@dataclass
class Photo:
    """The fields of an Immich asset that event detection and curation need."""

    id: str
    local_dt: datetime  # wall-clock time where the photo was taken (naive)
    utc_dt: datetime
    filename: str
    mime: str
    width: int
    height: int
    is_favorite: bool
    rating: int
    lat: float | None
    lon: float | None
    city: str | None
    state: str | None
    country: str | None
    make: str | None
    model: str | None
    people: list[Person] = field(default_factory=list)
    duplicate_id: str | None = None
    stack_id: str | None = None
    stack_primary_id: str | None = None
    checksum: str = ""

    @property
    def day(self):
        return self.local_dt.date()

    @property
    def has_gps(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def named_people(self) -> list[Person]:
        return [p for p in self.people if p.name]

    @property
    def is_stack_child(self) -> bool:
        return bool(self.stack_id) and self.stack_primary_id not in (None, self.id)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def photo_from_asset(a: dict[str, Any]) -> Photo | None:
    """Convert an AssetResponseDto into a Photo, or None if it should be ignored."""
    if a.get("type") != "IMAGE":
        return None
    if a.get("isTrashed") or a.get("isArchived") or a.get("isOffline"):
        return None
    if a.get("visibility") not in (None, "timeline"):
        return None  # archived, hidden (live-photo halves) or locked folder
    local = _parse_dt(a.get("localDateTime"))
    utc = _parse_dt(a.get("fileCreatedAt")) or local
    if local is None:
        return None
    exif = a.get("exifInfo") or {}
    stack = a.get("stack") or {}
    people = [
        Person(p["id"], (p.get("name") or "").strip())
        for p in a.get("people") or []
        if not p.get("isHidden")
    ]
    return Photo(
        id=a["id"],
        # localDateTime is the local wall clock time encoded with a Z suffix.
        local_dt=local.replace(tzinfo=None),
        utc_dt=utc.astimezone(timezone.utc) if utc.tzinfo else utc.replace(tzinfo=timezone.utc),
        filename=a.get("originalFileName") or "",
        mime=a.get("originalMimeType") or "",
        width=exif.get("exifImageWidth") or a.get("width") or 0,
        height=exif.get("exifImageHeight") or a.get("height") or 0,
        is_favorite=bool(a.get("isFavorite")),
        rating=exif.get("rating") or 0,
        lat=exif.get("latitude"),
        lon=exif.get("longitude"),
        city=exif.get("city") or None,
        state=exif.get("state") or None,
        country=exif.get("country") or None,
        make=exif.get("make") or None,
        model=exif.get("model") or None,
        people=people,
        duplicate_id=a.get("duplicateId"),
        stack_id=stack.get("id"),
        stack_primary_id=stack.get("primaryAssetId"),
        checksum=a.get("checksum") or "",
    )


_pinned: dict[str, str] = {}
_real_getaddrinfo = socket.getaddrinfo


def _getaddrinfo(host, *args, **kwargs):
    return _real_getaddrinfo(_pinned.get(host, host), *args, **kwargs)


def pin_host(hostname: str, ip: str) -> None:
    """Connect to `ip` whenever `hostname` is looked up, like curl's --resolve.

    For an Immich address Home Assistant's DNS can't look up: requests still
    sends the hostname for HTTPS (SNI) and checks the certificate against it,
    so certificate checks keep working.
    """
    _pinned[hostname] = ip
    socket.getaddrinfo = _getaddrinfo


def describe_error(err: Exception) -> str:
    """A plain-English reason a request to Immich failed, with what to try."""
    text = str(err)
    if isinstance(err, requests.exceptions.SSLError) or "CERTIFICATE_VERIFY_FAILED" in text:
        return (
            "its HTTPS certificate wasn't accepted. If you connect by IP address, set 'Immich IP address' and keep "
            "the hostname in 'Immich URL' instead; for a self-signed certificate, turn off 'Verify HTTPS certificate'"
        )
    if "Name or service not known" in text or "Temporary failure in name resolution" in text or "NameResolutionError" in text or "getaddrinfo failed" in text:
        return (
            "the hostname couldn't be looked up from inside Home Assistant. Set 'Immich IP address' to Immich's IP, "
            "or leave 'Immich URL' empty to use the Immich app directly"
        )
    if isinstance(err, requests.exceptions.ConnectTimeout) or "timed out" in text:
        return "the connection timed out"
    if isinstance(err, requests.exceptions.ConnectionError):
        return "nothing answered at that address and port"
    return text[:300]


class Immich:
    def __init__(self, url: str, api_key: str, timeout: float = 60, verify: bool = True):
        url = url.strip()
        if "://" not in url:
            url = "http://" + url
        self.base = url.rstrip("/")
        if not self.base.endswith("/api"):
            self.base += "/api"
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key, "Accept": "application/json"})
        self.session.verify = verify
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.timeout = timeout

    # -- plumbing ---------------------------------------------------------

    def _request(self, method: str, path: str, *, raw: bool = False, **kwargs) -> Any:
        url = f"{self.base}{path}"
        for attempt in range(4):
            try:
                # verify is passed per request: a session-level False is overridden by
                # REQUESTS_CA_BUNDLE if that's set (a requests quirk).
                resp = self.session.request(method, url, timeout=self.timeout, verify=self.session.verify, **kwargs)
            except requests.RequestException as err:
                # DNS and certificate errors won't fix themselves; don't retry them.
                permanent = isinstance(err, requests.exceptions.SSLError) or "resolution" in str(err).lower() \
                    or "not known" in str(err)
                if attempt == 3 or permanent:
                    raise ImmichError(f"{method} {path}: {describe_error(err)}") from err
                time.sleep(2**attempt)
                continue
            if resp.status_code >= 500 and attempt < 3:
                time.sleep(2**attempt)
                continue
            if resp.status_code >= 400:
                raise ImmichError(f"{method} {path}: HTTP {resp.status_code} {resp.text[:300]}")
            if raw:
                return resp.content
            if not resp.content:
                return None
            return resp.json()
        raise ImmichError(f"{method} {path}: gave up")

    def get(self, path, **kw):
        return self._request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self._request("POST", path, json=body, **kw)

    def put(self, path, body=None, **kw):
        return self._request("PUT", path, json=body, **kw)

    def patch(self, path, body=None, **kw):
        return self._request("PATCH", path, json=body, **kw)

    def delete(self, path, body=None, **kw):
        return self._request("DELETE", path, json=body, **kw)

    # -- server -------------------------------------------------------------

    def version(self) -> str:
        v = self.get("/server/version")
        return f"{v.get('major')}.{v.get('minor')}.{v.get('patch')}"

    def check_auth(self) -> None:
        self.get("/users/me")

    # -- search -------------------------------------------------------------

    def _paged_search(self, path: str, body: dict, limit: int | None = None) -> Iterator[dict]:
        body = dict(body)
        body.setdefault("size", PAGE_SIZE)
        seen = 0
        while True:
            result = self.post(path, body)["assets"]
            for item in result.get("items", []):
                yield item
                seen += 1
                if limit is not None and seen >= limit:
                    return
            if result.get("nextCursor"):
                body.pop("page", None)
                body["cursor"] = result["nextCursor"]
            elif result.get("nextPage"):
                body["page"] = int(result["nextPage"])
            else:
                return

    def all_photos(self, taken_after: datetime | None = None) -> list[Photo]:
        body: dict[str, Any] = {"type": "IMAGE", "withExif": True, "withPeople": True}
        if taken_after:
            body["takenAfter"] = taken_after.astimezone(timezone.utc).isoformat()
        photos = []
        for item in self._paged_search("/search/metadata", body):
            p = photo_from_asset(item)
            if p:
                photos.append(p)
        return photos

    def smart_search_ids(self, query: str, limit: int) -> list[str]:
        """Asset ids ranked by CLIP similarity to `query`, most similar first."""
        body = {"query": query, "type": "IMAGE", "size": min(PAGE_SIZE, limit)}
        return [a["id"] for a in self._paged_search("/search/smart", body, limit=limit)]

    # -- people ---------------------------------------------------------------

    def people(self) -> list[dict]:
        out, page = [], 1
        while True:
            resp = self.get("/people", params={"page": page, "size": 500, "withHidden": "false"})
            out.extend(resp.get("people", []))
            if not resp.get("hasNextPage"):
                return out
            page += 1

    # -- media ----------------------------------------------------------------

    def preview(self, asset_id: str) -> bytes:
        return self.get(f"/assets/{asset_id}/thumbnail", params={"size": "preview"}, raw=True)

    # -- albums and stacks ----------------------------------------------------

    def albums(self) -> list[dict]:
        return self.get("/albums") or []

    def album_exists(self, album_id: str) -> bool:
        try:
            self.get(f"/albums/{album_id}")
            return True
        except ImmichError as err:
            if "HTTP 400" in str(err) or "HTTP 404" in str(err):
                return False
            raise

    def create_album(self, name: str, description: str, asset_ids: list[str]) -> dict:
        return self.post(
            "/albums", {"albumName": name, "description": description, "assetIds": asset_ids}
        )

    def set_album_cover(self, album_id: str, asset_id: str) -> None:
        self.patch(f"/albums/{album_id}", {"albumThumbnailAssetId": asset_id})

    def add_to_album(self, album_id: str, asset_ids: list[str]) -> None:
        self.put(f"/albums/{album_id}/assets", {"ids": asset_ids})

    def delete_album(self, album_id: str) -> None:
        self.delete(f"/albums/{album_id}")

    def create_stack(self, asset_ids: list[str]) -> str:
        """Stack the assets; the first id becomes the stack's primary (cover) photo."""
        return self.post("/stacks", {"assetIds": asset_ids})["id"]

    def delete_stack(self, stack_id: str) -> None:
        self.delete(f"/stacks/{stack_id}")
