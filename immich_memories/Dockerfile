# Immich Memories for Home Assistant.
#
# Built from a slim Python image, pinned by digest for reproducible builds. The
# digest is a multi-arch manifest (amd64 + arm64), so FROM resolves to the right
# architecture at build time. The digest and the app `version` are updated
# automatically by .github/workflows/update-base-image.yml.
#
# Since Supervisor 2026.04.0 the BUILD_FROM arg is no longer injected, so we
# declare our own default here.
ARG BUILD_FROM=library/python@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
FROM ${BUILD_FROM}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tzdata so photo dates and the daily run time follow Home Assistant's time zone.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/requirements.txt .
RUN pip install -r requirements.txt

# OpenCV's YuNet face detector (MIT licence), checked against its known hash.
ARG YUNET_URL=https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
ARG YUNET_SHA256=8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
RUN mkdir -p /app/models \
    && python3 -c "import urllib.request; urllib.request.urlretrieve('${YUNET_URL}', '/app/models/yunet.onnx')" \
    && echo "${YUNET_SHA256}  /app/models/yunet.onnx" | sha256sum -c -
ENV YUNET_MODEL=/app/models/yunet.onnx

COPY app/immich_memories /app/immich_memories

CMD ["python3", "-m", "immich_memories"]

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Immich Memories for Home Assistant"
ARG BUILD_NAME="Immich Memories"
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
