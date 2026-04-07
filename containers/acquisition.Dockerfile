FROM python:3.12-slim-bookworm

ARG TAXON_WEAVER_REF=v.0.1.1
ARG TAXON_WEAVER_COMMIT=aff9709a82ac09fa3f97a71cca809f8e8f98c213
ARG NCBI_DATASETS_URL=https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/linux-amd64/datasets
ARG NCBI_DATAFORMAT_URL=https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/linux-amd64/dataformat

LABEL org.opencontainers.image.title="homorepeat-acquisition" \
      org.opencontainers.image.description="Pinned acquisition runtime for the HomoRepeat rebuild" \
      org.opencontainers.image.source="https://github.com/rafaelmdc/taxon-weaver" \
      org.opencontainers.image.vendor="HomoRepeat" \
      org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TAXONOMY_DB_PATH=/data/taxonomy/ncbi_taxonomy.sqlite

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        procps \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install "taxon-weaver @ git+https://github.com/rafaelmdc/taxon-weaver.git@${TAXON_WEAVER_COMMIT}" \
    && curl -fsSL "${NCBI_DATASETS_URL}" -o /usr/local/bin/datasets \
    && curl -fsSL "${NCBI_DATAFORMAT_URL}" -o /usr/local/bin/dataformat \
    && chmod +x /usr/local/bin/datasets /usr/local/bin/dataformat \
    && python --version \
    && taxon-weaver --help >/dev/null \
    && datasets version \
    && dataformat --help >/dev/null

RUN mkdir -p /work /data/taxonomy /data/ncbi-cache

COPY pyproject.toml README.md /opt/homorepeat/
COPY src /opt/homorepeat/src

RUN python -m pip install /opt/homorepeat

WORKDIR /work

ENV HOMOREPEAT_ACQUISITION_IMAGE=1 \
    TAXON_WEAVER_PINNED_REF=${TAXON_WEAVER_REF} \
    TAXON_WEAVER_PINNED_COMMIT=${TAXON_WEAVER_COMMIT}
