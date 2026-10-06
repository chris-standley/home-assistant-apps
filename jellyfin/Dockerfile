# Wrap the official Jellyfin image as a Home Assistant app.
#
# Tracks ghcr.io/jellyfin/jellyfin:latest, pinned by digest for reproducible
# builds. The digest is a multi-arch manifest (amd64 + arm64), so FROM resolves
# to the correct architecture at build time — no per-arch templating needed.
# The official image bundles jellyfin-ffmpeg with VA-API / QSV / NVENC support.
#
# The digest below and the app `version` are updated automatically by
# .github/workflows/update-base-image.yml when the upstream tag changes.
#
# Since Supervisor 2026.04.0 the BUILD_FROM arg is no longer injected, so we
# declare our own default here.
ARG BUILD_FROM=ghcr.io/jellyfin/jellyfin@sha256:c3efa69a22f2691fc88d6bb035e87a8560e395a6047f062fb381c61c3185e8f5
FROM ${BUILD_FROM}

# The upstream image already defines the entrypoint that launches Jellyfin, so
# we only attach app metadata.
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Jellyfin (Intel / AMD) for Home Assistant"
ARG BUILD_NAME="Jellyfin (Intel / AMD)"
ARG BUILD_REF
ARG BUILD_VERSION

LABEL \
  io.hass.name="${BUILD_NAME}" \
  io.hass.description="${BUILD_DESCRIPTION}" \
  io.hass.arch="${BUILD_ARCH}" \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  maintainer="Chris Standley <chris@cstandley.com>" \
  org.opencontainers.image.source="https://github.com/chris-standley/home-assistant-apps"
