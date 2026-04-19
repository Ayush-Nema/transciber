# Video Transcriber

AI-powered video transcription app for YouTube, Instagram, and Facebook. Optimized for Hindi and Indian language content using OpenAI's latest transcription models.

## Features

- **Multi-platform support** — YouTube, Instagram, Facebook (public videos, reels, shorts)
- **Two ASR engines** — OpenAI `gpt-4o-mini-transcribe` (default) or local faster-whisper (Docker)
- **YouTube subtitle fast-path** — Automatically extracts existing YouTube subtitles/auto-captions when available, skipping ASR entirely for faster results
- **Optional LLM post-correction** — GPT-4o-mini cleans up transcription errors, especially for Hindi/Hinglish content (toggle on/off)
- **Audio preprocessing** — FFmpeg-based highpass filtering and two-pass loudness normalization before transcription
- **Real-time progress** — SSE-based live updates during every pipeline stage
- **Video player** — Embedded HTML5 player with seek controls and transcript sync
- **Dual transcript view** — Toggle between clean paragraph view and timestamped segment view with click-to-seek
- **Segment selection** — Transcribe a specific time range of the video
- **Auto-split** — Break long videos into chunks for efficient processing
- **MP3 download** — Download the video's audio as MP3
- **Hindi-first** — Optimized for Hindi with support for Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Punjabi, Urdu, and English

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend   │───>│     Backend      │───>│  ASR Service     │
│  React+Vite  │    │     FastAPI      │    │ faster-whisper   │
│  :5173       │    │     :8000        │    │  :8001 (optional)│
└─────────────┘    └──────┬───────────┘    └─────────────────┘
                          │
                          ├──> yt-dlp (video download + subtitle extraction)
                          ├──> ffmpeg (audio extraction + preprocessing)
                          ├──> OpenAI API (gpt-4o-mini-transcribe + GPT-4o-mini)
                          └──> SQLite (job storage)
```

### Transcription Pipeline

```
URL → [Check YouTube subtitles] → Download video → Extract audio
                                         │
              ┌──────────────────────────┘
              ▼
     Preprocess audio (highpass + loudness normalization)
              │
              ▼
     Transcribe (OpenAI / Docker)
              │                              OR   Use extracted subtitles
              ▼
     LLM post-correction (optional) → Done
```

For YouTube videos with existing subtitles, the pipeline skips audio extraction, preprocessing, and ASR entirely. The video download runs concurrently in the background so the transcript is returned faster.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An OpenAI API key (for the default ASR engine and LLM post-correction)

### 1. Configure environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-xxxxx
```

See `.env.example` for all available options.

### 2. Build and run

```bash
make build
```

This builds and starts the frontend and backend containers. Open **http://localhost:5173** in your browser.

### 3. (Optional) Run with local ASR

To also start the local faster-whisper container:

```bash
docker compose --profile local-asr up --build -d
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(required)_ | OpenAI API key for transcription and LLM post-correction |
| `OPENAI_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` | Transcription model (see options below) |
| `ASR_MODE` | `openai` | ASR backend: `openai` or `docker` |
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper model size when using Docker ASR |

### OpenAI Transcription Models

| Model | Hindi Accuracy | Segment Timestamps | Cost |
|---|---|---|---|
| `gpt-4o-mini-transcribe` | Excellent | No (use subtitle fast-path or paragraph view) | ~$0.003/min |
| `gpt-4o-transcribe` | Best | No | ~$0.006/min |
| `whisper-1` | Good | Yes (verbose_json with timestamps) | ~$0.006/min |

The default `gpt-4o-mini-transcribe` offers the best accuracy-to-cost ratio, especially for Hindi and other Indian languages. Use `whisper-1` if you specifically need segment-level timestamps from the ASR engine.

To change the model, set `OPENAI_TRANSCRIPTION_MODEL` in your `.env` file or in docker-compose.

## Usage

1. Paste a YouTube, Instagram, or Facebook video URL
2. Click **Fetch Info** to preview video metadata
3. (Optional) Configure options:
   - **ASR Engine** — OpenAI (default) or Docker (faster-whisper)
   - **Language** — Hindi (default), English, or other supported languages
   - **Time range** — Transcribe a specific portion of the video
   - **Split duration** — Break long audio into chunks (e.g., 600s)
   - **Context** — Guide both ASR and LLM with expected vocabulary (e.g., "Hindi news about Union Budget, GST")
   - **LLM Cleanup** — Toggle GPT-4o-mini post-correction on/off
4. Click **Transcribe**
5. Watch real-time progress — the pipeline shows each stage (subtitle check, download, audio extraction, transcription, LLM cleanup)
6. View the result in **Paragraph** mode (default) or toggle to **Timestamps** mode (click any segment to jump in the video)

## Makefile Commands

| Command | Description |
|---|---|
| `make build` | Build and start all containers |
| `make up` | Start containers (no rebuild) |
| `make down` | Stop containers |
| `make restart` | Full restart with rebuild |
| `make logs` | Follow container logs |
| `make lint` | Run ruff linter on backend |
| `make dev` | Run backend directly (no Docker) |
| `make purge-data` | Remove downloaded videos/audio and Docker volume |
| `make clean` | Full cleanup — stop containers, remove volumes and images |

## Pre-commit Hook

A git pre-commit hook is set up that runs automatically on every commit:

1. **Secret detection** — Scans staged files for leaked API keys (OpenAI `sk-*`, GitHub `ghp_*`, HuggingFace `hf_*`, Google `AIza*`, private keys). Blocks the commit if a secret is found.
2. **Python formatting** — Runs `ruff format` on staged `.py` files (4-space indent, double quotes, 120-char line length — matches PyCharm defaults).
3. **Python linting** — Runs `ruff check --fix` to catch unused imports, unsorted imports, and common errors. Auto-fixes are re-staged.

To manually run the same checks:

```bash
uv run ruff format backend/       # format
uv run ruff check --fix backend/  # lint + auto-fix
```

Ruff configuration lives in `pyproject.toml` under `[tool.ruff]`.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs/video-info` | Fetch video metadata without transcribing |
| `POST` | `/api/jobs/` | Create a transcription job |
| `GET` | `/api/jobs/{id}` | Get job status and results |
| `GET` | `/api/jobs/{id}/stream` | SSE progress stream |
| `GET` | `/api/video/{id}` | Serve downloaded video file |
| `GET` | `/api/video/{id}/mp3` | Download audio as MP3 |

### Create Job Request

```json
{
  "url": "https://youtube.com/watch?v=...",
  "asr_provider": "openai",
  "language": "hi",
  "start_time": null,
  "end_time": null,
  "split_duration": null,
  "context": "Hindi discussion about technology and startups",
  "llm_cleanup": true
}
```

## Development (without Docker)

### Backend

```bash
uv pip install -r pyproject.toml
# Requires ffmpeg installed locally
make dev
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### ASR Service (optional, for local mode)

```bash
cd asr-service
uv venv .venv && source .venv/bin/activate
uv pip install -r pyproject.toml
python main.py
```

## Tech Stack

- **Frontend**: React 18, Vite
- **Backend**: FastAPI, SQLAlchemy (async), aiosqlite, yt-dlp, ffmpeg, loguru
- **ASR**: OpenAI gpt-4o-mini-transcribe (default) / faster-whisper (Docker)
- **LLM**: GPT-4o-mini for transcription post-correction (optional)
- **Linting**: Ruff (format + lint), pre-commit hook
- **Package Management**: uv (Python), npm (Node.js)
- **Infra**: Docker Compose, SSE (Server-Sent Events), SQLite
