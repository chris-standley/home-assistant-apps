# Changelog

## 0.1.7 — 2026-10-28

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb`


## 0.1.6 — 2026-10-27

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:b3575dcf816cdacc5292df77a6e3e59b8941631078373a045efa2ac1e9c5c3b2`


## 0.1.5 — 2026-10-25

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962`


## 0.1.4 — 2026-10-22

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:57b29a7c050c4e679e4bea572e14b3965cf4b5839de2da49d55e49ffc4024f39`


## 0.1.3 — 2026-10-21

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:cf50a4f6ac4f026458b08d5222023d700ac806410dff5e9ca8728fa44f2b850f`


## 0.1.2

- Fewer similar photos. Similar shots are now matched by their colours and
  layout as well as fine detail, so reframed or zoomed shots of the same thing
  are stacked, not just bursts. Albums also skip a photo when they already have
  one of the same scene from around the same time, so they show a range of
  moments instead of repeats. Album sizes are unchanged.
- New **Similar photo filtering** option: light, normal (default) or strong.
- Fixed album names calling a day someone's birthday when it isn't: a party or
  a cake no longer makes the AI (or the template) name it after a birthday.
- Photos are analysed again once after this update, to measure what they look
  like.

## 0.1.1

- **Immich IP address** option: connect to Immich by IP while keeping its
  hostname, for when Home Assistant can't look the hostname up. HTTPS
  certificate checks keep working.
- **Verify HTTPS certificate** option, to allow self-signed certificates.
- If the Immich URL can't be reached, the app now falls back to the Immich app
  on this Home Assistant, and the log says why the URL failed (hostname not
  found, certificate not accepted, nothing listening) and what to try.

## 0.1.0

- First release. Finds trips, days out, holidays, birthdays and unusually busy
  days in Immich and makes an album for each, with a friendly name (optionally
  polished by Home Assistant's AI).
- Leaves out screenshots, receipts and paperwork, and photos of jobs around the
  house.
- Stacks near-identical shots with the best one on top: most people facing the
  camera with their eyes open, then the sharpest.
- Collections that grow each year: holiday seasons (*Christmas through the
  years*), birthdays, holidays in a country (*Holidays in Norway*) and repeat
  visits to an area (*Trips to the Lake District*).
- Dry run, and a one-switch undo that removes everything it made.
