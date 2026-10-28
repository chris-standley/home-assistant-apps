# Ticket to Ride Scorer for Home Assistant.
#
# Built from a slim Python image, pinned by digest for reproducible builds. The
# digest is a multi-arch manifest (amd64 + arm64), so FROM resolves to the right
# architecture at build time. The digest and the app `version` are updated
# automatically by .github/workflows/update-base-image.yml.
#
# Since Supervisor 2026.04.0 the BUILD_FROM arg is no longer injected, so we
# declare our own default here.
ARG BUILD_FROM=library/python@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb
FROM ${BUILD_FROM}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY app/requirements.txt .
RUN pip install -r requirements.txt

COPY app/ticket_to_ride /app/ticket_to_ride

EXPOSE 8099
CMD ["python3", "-m", "ticket_to_ride"]

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Ticket to Ride Scorer for Home Assistant"
ARG BUILD_NAME="Ticket to Ride Scorer"
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
