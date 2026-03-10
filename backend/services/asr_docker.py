"""ASR client for the Docker-hosted faster-whisper service."""
import logging
from pathlib import Path
from typing import Callable, Awaitable

import httpx

from config import ASR_DOCKER_URL

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(timeout=600.0, connect=30.0)


async def transcribe_audio(
    audio_path: Path,
    language: str = "hi",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """
    Send audio to Docker ASR service and get transcription.
    Returns: {"text": str, "segments": [{"start": float, "end": float, "text": str}], "language": str}
    """
    if on_progress:
        await on_progress(0, "Sending audio to ASR service (faster-whisper)...")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            data = {"language": language}

            response = await client.post(
                f"{ASR_DOCKER_URL}/transcribe",
                files=files,
                data=data,
            )

        if response.status_code != 200:
            raise RuntimeError(f"ASR service error ({response.status_code}): {response.text}")

        result = response.json()

    if on_progress:
        await on_progress(100, "Transcription complete (faster-whisper).")

    return result


async def transcribe_audio_chunked(
    audio_chunks: list[Path],
    language: str = "hi",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """Transcribe multiple audio chunks and merge results."""
    all_text = []
    all_segments = []
    time_offset = 0.0

    for i, chunk_path in enumerate(audio_chunks):
        pct = (i / len(audio_chunks)) * 100
        if on_progress:
            await on_progress(pct, f"Transcribing chunk {i+1}/{len(audio_chunks)}...")

        result = await transcribe_audio(chunk_path, language=language)
        all_text.append(result.get("text", ""))

        for seg in result.get("segments", []):
            all_segments.append({
                "start": seg["start"] + time_offset,
                "end": seg["end"] + time_offset,
                "text": seg["text"],
            })

        # Get chunk duration from last segment
        if result.get("segments"):
            time_offset += result["segments"][-1]["end"]

    if on_progress:
        await on_progress(100, "All chunks transcribed.")

    return {
        "text": " ".join(all_text),
        "segments": all_segments,
        "language": language,
    }
