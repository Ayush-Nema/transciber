# ── Build stage: install deps with uv ──
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create venv at /opt/venv so it survives the volume mount in docker-compose
RUN uv venv /opt/venv

WORKDIR /build
COPY pyproject.toml ./

# Install deps into the venv using uv pip (fast, no lockfile needed in Docker)
RUN VIRTUAL_ENV=/opt/venv uv pip install -r pyproject.toml

# ── Runtime stage ──
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

RUN mkdir -p data/videos data/audio

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
