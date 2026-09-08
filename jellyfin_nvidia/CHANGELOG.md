# Changelog

## 1.0.1 — 2026-09-08

- Updated the base image to a new upstream build (tracks the `latest` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:74f4d87d9cf262c52d62be6be265c0355c6a7e21d0477ab6c654a49a4f8b1fd4`


## 1.0.0

- Initial release. Jellyfin media system with NVIDIA NVENC hardware
  transcoding, wrapping the official `ghcr.io/jellyfin/jellyfin` image. Requires
  a host with NVIDIA drivers and GPU device access (see the documentation).
  Ingress enabled for authenticated remote access through Home Assistant.
