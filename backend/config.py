import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent  # one level up from backend/
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "transcriber.db"

# Ensure directories exist
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# ASR configuration
ASR_MODE = os.getenv("ASR_MODE", "openai")  # "openai" or "docker"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
ASR_DOCKER_URL = os.getenv("ASR_DOCKER_URL", "http://asr-service:8001")

# Video settings
MAX_VIDEO_DURATION_SECONDS = 3 * 3600  # 3 hours max
DEFAULT_SPLIT_DURATION_SECONDS = 600    # 10 minutes default split


def openai_headers() -> dict:
    """Common Authorization headers for OpenAI API calls."""
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
