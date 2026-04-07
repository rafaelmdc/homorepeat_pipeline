FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="homorepeat-detection" \
      org.opencontainers.image.description="Pinned detection runtime for the HomoRepeat rebuild" \
      org.opencontainers.image.source="https://github.com/rafaelmdc/homorepeat" \
      org.opencontainers.image.vendor="HomoRepeat" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        procps \
    && rm -rf /var/lib/apt/lists/*

RUN python --version

RUN mkdir -p /work

COPY pyproject.toml README.md /opt/homorepeat/
COPY src /opt/homorepeat/src

RUN python -m pip install /opt/homorepeat

WORKDIR /work

ENV HOMOREPEAT_DETECTION_IMAGE=1
