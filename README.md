# Video Transcriber

AI-powered video transcription app for YouTube, Instagram, and Facebook. Optimized for Hindi and Indian language content using OpenAI's latest transcription models.

## Features

- **Multi-platform support** — YouTube, Instagram, Facebook (public videos, reels, shorts)
- **Three ASR engines** — OpenAI `gpt-4o-mini-transcribe` (default), local faster-whisper (Docker), or HuggingFace Inference API
- **YouTube subtitle fast-path** — Automatically extracts existing YouTube subtitles/auto-captions when available, skipping ASR entirely for faster results
- **LLM post-correction** — GPT-4o-mini cleans up transcription errors, especially for Hindi/Hinglish content
- **Audio preprocessing** — FFmpeg-based noise reduction and loudness normalization before transcription
- **Real-time progress** — SSE-based live updates during every pipeline stage
- **Video player** — Embedded HTML5 player with play/pause/seek controls
- **Dual transcript view** — Toggle between clean paragraph view (default) and timestamped segment view with click-to-seek
- **Segment selection** — Transcribe a specific time range of the video
- **Auto-split** — Break long videos into chunks for efficient processing
- **Mind-map** — Auto-generated Mermaid mind-map from transcription content
- **Whisper prompt priming** — Optional prompt field to guide ASR with expected vocabulary
- **Hindi-first** — Optimized for Hindi with support for Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada, Punjabi, Urdu, and English

## Architecture

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend   │───▶│     Backend      │───▶│  ASR Service     │
│  React+Vite  │    │     FastAPI      │    │ faster-whisper   │
│  :5173       │    │     :8000        │    │  :8001 (optional)│
└─────────────┘    └──────┬───────────┘    └─────────────────┘
                          │
                          ├──▶ yt-dlp (video download + subtitle extraction)
                          ├──▶ ffmpeg (audio extraction + preprocessing)
                          ├──▶ OpenAI API (gpt-4o-mini-transcribe + GPT-4o-mini)
                          ├──▶ SQLite (job storage)
                          └──▶ HuggingFace API (alt ASR)
```

### Transcription Pipeline

```
URL → [Check YouTube subtitles] → Download video → Extract audio
                                         │
              ┌──────────────────────────┘
              ▼
     Preprocess audio (noise reduction + normalization)
              │
              ▼
     Transcribe (OpenAI / Docker / HuggingFace)
              │                              OR   Use extracted subtitles
              ▼
     LLM post-correction (GPT-4o-mini)
              │
              ▼
     Generate mind-map → Done
```

For YouTube videos with existing subtitles, the pipeline skips audio extraction, preprocessing, and ASR entirely — jumping straight from subtitle extraction to LLM post-correction.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An OpenAI API key (for the default ASR engine and LLM post-correction)

### 1. Configure environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-xxxxx
HF_TOKEN=hf_xxxxx          # Optional, for HuggingFace ASR mode
```

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
| `ASR_MODE` | `openai` | ASR backend: `openai`, `docker`, or `huggingface` |
| `HF_TOKEN` | _(empty)_ | HuggingFace API token (optional, for HF ASR mode) |
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
   - **ASR Engine** — OpenAI (default), Docker, or HuggingFace
   - **Language** — Hindi (default), English, or other supported languages
   - **Time range** — Transcribe a specific portion of the video
   - **Split duration** — Break long audio into chunks (e.g., 600s)
   - **Whisper Prompt** — Guide the model with expected vocabulary (e.g., "Hindi news discussion about GST, fiscal deficit")
   - **Topic Hint** — Context for LLM post-correction (e.g., "Cricket commentary", "Bollywood review")
4. Click **Transcribe**
5. Watch real-time progress — the pipeline shows each stage (subtitle check, download, audio extraction, transcription, LLM cleanup, mind-map)
6. View the result in **Paragraph** mode (default, clean readable text) or toggle to **Timestamps** mode (click any segment to jump in the video)
7. Switch to the **Mind Map** tab for a visual topic summary

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

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/jobs/video-info` | Fetch video metadata without transcribing |
| `POST` | `/api/jobs/` | Create a transcription job |
| `GET` | `/api/jobs/{id}` | Get job status and results |
| `GET` | `/api/jobs/{id}/stream` | SSE progress stream |
| `GET` | `/api/jobs/` | List recent jobs |
| `GET` | `/api/video/{id}` | Serve downloaded video file |
| `DELETE` | `/api/jobs/{id}` | Delete a job |

### Create Job Request

```json
{
  "url": "https://youtube.com/watch?v=...",
  "asr_provider": "openai",
  "language": "hi",
  "start_time": null,
  "end_time": null,
  "split_duration": null,
  "prompt": "Hindi discussion about technology and startups",
  "context_hint": "Tech podcast"
}
```

## Development (without Docker)

### Backend

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -r pyproject.toml
# Requires ffmpeg installed locally
uvicorn main:app --reload --port 8000
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

- **Frontend**: React 18, Vite, Mermaid.js
- **Backend**: FastAPI, SQLAlchemy (async), aiosqlite, yt-dlp, ffmpeg
- **ASR**: OpenAI gpt-4o-mini-transcribe (default) / faster-whisper (Docker) / HuggingFace Inference API
- **LLM**: GPT-4o-mini for transcription post-correction
- **Package Management**: uv (Python), npm (Node.js)
- **Infra**: Docker Compose, SSE (Server-Sent Events), SQLite
