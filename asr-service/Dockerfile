# ── Build stage: install deps with uv ──
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN uv venv /opt/venv

WORKDIR /build
COPY pyproject.toml ./

RUN VIRTUAL_ENV=/opt/venv uv pip install -r pyproject.toml

# ── Runtime stage ──
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY main.py .

# Whisper model config
ARG WHISPER_MODEL_SIZE=base
ENV WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE}
ENV WHISPER_DEVICE=cpu
ENV WHISPER_COMPUTE_TYPE=int8

# Download model at build time so container starts fast
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL_SIZE}', device='cpu', compute_type='int8')"

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
