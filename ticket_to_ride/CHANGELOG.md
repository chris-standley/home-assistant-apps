# Changelog

## 0.1.2 — 2026-10-27

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:b3575dcf816cdacc5292df77a6e3e59b8941631078373a045efa2ac1e9c5c3b2`


## 0.1.1 — 2026-10-25

- Updated the base image to a new upstream build (tracks the `3.13-slim` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962`


## 0.1.0

- First release. Photograph the board and each player's destination tickets
  and get everyone's final score: route points, completed and missed tickets,
  the longest-route bonus, and (Europe) unused stations.
- USA and Europe maps. On Europe, stations borrow the route that scores best.
- Photos are read by Home Assistant's AI (any AI Task entity that can see
  images). Every route and ticket can be checked and fixed by tapping, or
  entered by hand without AI.
- Scoring runs on the phone, so it's instant and keeps working if the
  connection to Home Assistant drops.
