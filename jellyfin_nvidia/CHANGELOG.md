# Changelog

## 1.0.3 — 2026-10-06

- Updated the base image to a new upstream build (tracks the `latest` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:c3efa69a22f2691fc88d6bb035e87a8560e395a6047f062fb381c61c3185e8f5`


## 1.0.2 — 2026-09-15

- Updated the base image to a new upstream build (tracks the `latest` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:008ec8024bdaaa6f0a3f0de468e185633eeba9d67c56936e8dbf5ef6b8d6200f`


## 1.0.1 — 2026-09-08

- Updated the base image to a new upstream build (tracks the `latest` tag).
  This refreshes the bundled runtime (ffmpeg / OS / GPU libraries).
  Pinned digest: `sha256:74f4d87d9cf262c52d62be6be265c0355c6a7e21d0477ab6c654a49a4f8b1fd4`


## 1.0.0

- Initial release. Jellyfin media system with NVIDIA NVENC hardware
  transcoding, wrapping the official `ghcr.io/jellyfin/jellyfin` image. Requires
  a host with NVIDIA drivers and GPU device access (see the documentation).
  Ingress enabled for authenticated remote access through Home Assistant.
