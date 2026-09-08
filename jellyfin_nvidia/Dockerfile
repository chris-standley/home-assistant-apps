# Wrap the official Jellyfin image as a Home Assistant app (NVIDIA variant).
#
# Same official image as the Intel/AMD app — ghcr.io/jellyfin/jellyfin bundles
# jellyfin-ffmpeg with NVENC/CUDA support — pinned by digest. This variant just
# maps the NVIDIA device nodes (in config.yaml) and declares the NVIDIA runtime
# capabilities below. The matching NVIDIA kernel driver must be on the host.
#
# The digest below and the app `version` are updated automatically by
# .github/workflows/update-base-image.yml when the upstream tag changes.
#
# Since Supervisor 2026.04.0 the BUILD_FROM arg is no longer injected, so we
# declare our own default here.
ARG BUILD_FROM=ghcr.io/jellyfin/jellyfin@sha256:74f4d87d9cf262c52d62be6be265c0355c6a7e21d0477ab6c654a49a4f8b1fd4
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Jellyfin (NVIDIA) for Home Assistant"
ARG BUILD_NAME="Jellyfin (NVIDIA)"
ARG BUILD_REF
ARG BUILD_VERSION

# Hint the NVIDIA container runtime (if the host uses nvidia-container-toolkit)
# about the capabilities this container needs.
ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

LABEL \
  io.hass.name="${BUILD_NAME}" \
  io.hass.description="${BUILD_DESCRIPTION}" \
  io.hass.arch="${BUILD_ARCH}" \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  maintainer="Chris Standley <chris@cstandley.com>" \
  org.opencontainers.image.source="https://github.com/chris-standley/home-assistant-apps"
