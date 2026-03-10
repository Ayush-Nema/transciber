import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "transcriber.db"

# Ensure directories exist
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# ASR configuration
ASR_MODE = os.getenv("ASR_MODE", "openai")  # "openai", "docker", or "huggingface"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# Transcription model: "gpt-4o-mini-transcribe" (better accuracy, esp. Hindi)
#                      "gpt-4o-transcribe" (best accuracy, higher cost)
#                      "whisper-1" (legacy, supports segment timestamps)
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
ASR_DOCKER_URL = os.getenv("ASR_DOCKER_URL", "http://asr-service:8001")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "openai/whisper-large-v3")
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
HF_TOKEN = os.getenv("HF_TOKEN", "")  # Optional, for higher rate limits

# Video settings
MAX_VIDEO_DURATION_SECONDS = 3 * 3600  # 3 hours max
DEFAULT_SPLIT_DURATION_SECONDS = 600    # 10 minutes default split
