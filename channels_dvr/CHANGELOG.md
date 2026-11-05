# Changelog

## 1.0.3 — 2026-11-05

- Updated the base image to a new upstream build (tracks the `latest` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:8b430c5865c95378750226f0198c49332d084c276485053146c8ebfc020f0abf`


## 1.0.2

- Pin the base image by digest for reproducible builds, with automated
  base-image updates via CI (a new version is published when the upstream
  image changes).
- Fix the Web UI link so Home Assistant Supervisor accepts the configuration.

## 1.0.0

- Initial release. Channels DVR Server with Intel Quick Sync / AMD VA-API
  hardware transcoding, wrapping the official `fancybits/channels-dvr` image.
