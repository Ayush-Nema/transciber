# Video Transcriber

AI-powered video transcription app for YouTube, Instagram, and Facebook. Optimized for Hindi language content with support for 10+ Indian languages.

## Features

- **Multi-platform support** — YouTube, Instagram, Facebook (public videos/reels/shorts)
- **Dual ASR engines** — Local faster-whisper (Docker) or HuggingFace API (cloud)
- **Real-time progress** — SSE-based live updates during transcription
- **Video player** — Embedded player with play/pause/seek controls
- **Segment selection** — Transcribe a specific portion of the video
- **Auto-split** — Break long videos into chunks for efficient processing
- **Timestamped output** — Click any segment to jump to that point in the video
- **Mind-map** — Auto-generated Mermaid mind-map from transcription content
- **Hindi-first** — Extra emphasis on Hindi language with support for Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Punjabi, Urdu

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Frontend   │───▶│   Backend    │───▶│  ASR Service     │
│  React+Vite  │    │   FastAPI    │    │ faster-whisper   │
│  :5173       │    │   :8000      │    │  :8001           │
└─────────────┘    └──────┬───────┘    └─────────────────┘
                          │
                          ├──▶ yt-dlp (video download)
                          ├──▶ ffmpeg (audio extraction)
                          ├──▶ SQLite (job storage)
                          └──▶ HuggingFace API (alt ASR)
```

## Quick Start

### Prerequisites
- Docker & Docker Compose

### Option 1: Full Stack with Local ASR (recommended)

```bash
docker compose up --build
```

This starts all 3 services. The ASR model (~150MB base) is downloaded during the Docker build.

Open **http://localhost:5173** in your browser.

### Option 2: HuggingFace API Only (no GPU/heavy container needed)

```bash
# Optional: set HF token for higher rate limits
export HF_TOKEN=hf_xxxxx

docker compose -f docker-compose.yml -f docker-compose.hf.yml up --build
```

This skips the ASR container and uses the free HuggingFace Inference API instead.

## Configuration

Copy `.env.example` to `.env` and edit as needed:

| Variable | Default | Description |
|---|---|---|
| `HF_TOKEN` | _(empty)_ | HuggingFace API token (optional, for higher rate limits) |
| `WHISPER_MODEL_SIZE` | `base` | Model size: `tiny` (~75MB), `base` (~150MB), `small` (~500MB) |
| `ASR_MODE` | `docker` | ASR backend: `docker` or `huggingface` |

### Model Size Guide

| Model | Size | Hindi Accuracy | Speed (1min audio) | RAM |
|---|---|---|---|---|
| `tiny` | ~75MB | Fair | ~5s | ~500MB |
| `base` | ~150MB | Good | ~10s | ~1GB |
| `small` | ~500MB | Very Good | ~30s | ~2GB |

For Hindi, `base` or `small` is recommended.

## Usage

1. Paste a YouTube/Instagram/Facebook URL
2. Click **Fetch Info** to preview video metadata
3. (Optional) Set language, time range, or split duration
4. Choose ASR engine (Docker or HuggingFace)
5. Click **Transcribe**
6. Watch real-time progress via SSE updates
7. View timestamped transcription — click segments to jump in video
8. Switch to Mind Map tab for a visual summary

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs/video-info` | Fetch video metadata |
| `POST` | `/api/jobs/` | Create transcription job |
| `GET` | `/api/jobs/{id}` | Get job status/results |
| `GET` | `/api/jobs/{id}/stream` | SSE progress stream |
| `GET` | `/api/jobs/` | List recent jobs |
| `GET` | `/api/video/{id}` | Serve downloaded video |
| `DELETE` | `/api/jobs/{id}` | Delete a job |

## Development (without Docker)

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Requires ffmpeg installed locally
uvicorn main:app --reload --port 8000
```

### ASR Service
```bash
cd asr-service
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Frontend**: React 18, Vite, Mermaid.js
- **Backend**: FastAPI, SQLAlchemy (async), yt-dlp, ffmpeg
- **ASR**: faster-whisper (CTranslate2) / HuggingFace Inference API
- **Infra**: Docker Compose, SSE (Server-Sent Events)
