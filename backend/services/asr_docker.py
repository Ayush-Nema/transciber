"""ASR client for the Docker-hosted faster-whisper service."""

from pathlib import Path
from typing import Awaitable, Callable

import httpx

from backend.config import ASR_DOCKER_URL
from backend.services.asr_utils import transcribe_chunked

TIMEOUT = httpx.Timeout(timeout=600.0, connect=30.0)


async def transcribe_audio(
    audio_path: Path,
    language: str = "auto",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """
    Send audio to Docker ASR service and get transcription.
    Returns: {"text": str, "segments": [{"start": float, "end": float, "text": str}], "language": str}
    """
    if on_progress:
        await on_progress(0, "Sending audio to ASR service (faster-whisper)...")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (audio_path.name, f, "audio/wav")}
                data = {"language": language}

                response = await client.post(
                    f"{ASR_DOCKER_URL}/transcribe",
                    files=files,
                    data=data,
                )
    except httpx.ConnectError:
        raise RuntimeError(f"Cannot connect to ASR service at {ASR_DOCKER_URL}. Start it with: make up-asr")

    if response.status_code != 200:
        raise RuntimeError(f"ASR service error ({response.status_code}): {response.text}")

    result = response.json()

    if on_progress:
        await on_progress(100, "Transcription complete (faster-whisper).")

    return result


async def transcribe_audio_chunked(
    audio_chunks: list[Path],
    language: str = "auto",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """Transcribe multiple audio chunks and merge results."""
    return await transcribe_chunked(
        transcribe_audio,
        audio_chunks,
        "faster-whisper",
        language=language,
        on_progress=on_progress,
    )
