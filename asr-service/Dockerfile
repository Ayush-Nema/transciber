# ── Build stage: resolve deps with uv ──
FROM python:3.11-slim AS builder

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy project metadata only (cache-friendly layer)
COPY pyproject.toml ./

# Resolve lockfile and install deps into a virtual env
RUN uv lock && \
    uv sync --no-dev --no-install-project

# ── Runtime stage ──
FROM python:3.11-slim

# libgomp required by CTranslate2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY main.py .

# Whisper model config
ARG WHISPER_MODEL_SIZE=base
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

# HuggingFace token — needed to download models
# Passed as build arg from docker-compose, also set at runtime
ARG HF_TOKEN=""
ENV HF_TOKEN=${HF_TOKEN}

# Download model at build time so container starts fast
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
