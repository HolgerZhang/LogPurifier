# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-dev --no-cache

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r logpurifier -g 1000 \
    && useradd -r -u 1000 -g logpurifier -d /app -s /sbin/nologin logpurifier \
    && mkdir -p /app/data /app/artifacts /app/logs \
    && chown -R logpurifier:logpurifier /app

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /usr/local/bin/uv
COPY --from=builder --chown=logpurifier:logpurifier /build/.venv /app/.venv

COPY --chown=logpurifier:logpurifier pyproject.toml uv.lock ./
COPY --chown=logpurifier:logpurifier src/ ./src/
COPY --chown=logpurifier:logpurifier third_party/ ./third_party/
COPY --chown=logpurifier:logpurifier scripts/ ./scripts/
COPY --chown=logpurifier:logpurifier README.md ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER logpurifier

VOLUME ["/app/data", "/app/artifacts", "/app/logs"]

ENTRYPOINT ["uv", "run", "python", "scripts/run_ad.py"]
CMD ["--help"]
