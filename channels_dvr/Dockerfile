# Wrap the official Channels DVR image as a Home Assistant app.
#
# Tracks the fancybits/channels-dvr:latest tag, pinned by digest for
# reproducible builds. The digest is a multi-arch manifest (amd64 + arm64), so
# FROM resolves to the correct architecture at build time — no per-arch
# templating needed.
#
# The digest below and the app `version` are updated automatically by
# .github/workflows/update-base-image.yml when the upstream tag changes.
#
# Since Supervisor 2026.04.0 the BUILD_FROM arg is no longer injected, so we
# declare our own default here.
ARG BUILD_FROM=fancybits/channels-dvr@sha256:8b430c5865c95378750226f0198c49332d084c276485053146c8ebfc020f0abf
FROM ${BUILD_FROM}

# The upstream image already defines ENTRYPOINT/CMD that launch the DVR server,
# so we intentionally do not override them — we only attach app metadata.

# Build args supplied by the Home Assistant builder (unused but kept for
# compatibility with `docker build` invocations).
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Channels DVR Server for Home Assistant"
ARG BUILD_NAME="Channels DVR"
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
