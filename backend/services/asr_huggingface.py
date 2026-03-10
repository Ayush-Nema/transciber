"""ASR client using HuggingFace Inference API (free tier)."""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable

import httpx

from config import HF_API_URL, HF_TOKEN

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(timeout=300.0, connect=30.0)
MAX_CHUNK_SIZE_MB = 10  # HF free tier limit
MAX_RETRIES = 3
RETRY_DELAY = 20  # seconds (model loading time)


async def transcribe_audio(
    audio_path: Path,
    language: str = "hi",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """
    Send audio to HuggingFace Inference API.
    Returns: {"text": str, "segments": [], "language": str}
    Note: HF Inference API returns full text, segments are not available in free tier.
    """
    if on_progress:
        await on_progress(0, "Sending audio to HuggingFace Whisper API...")

    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_CHUNK_SIZE_MB:
        logger.warning(f"Audio file {file_size_mb:.1f}MB exceeds {MAX_CHUNK_SIZE_MB}MB limit")

    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(MAX_RETRIES):
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            response = await client.post(
                HF_API_URL,
                content=audio_data,
                headers={**headers, "Content-Type": "audio/wav"},
            )

            if response.status_code == 200:
                result = response.json()
                text = result.get("text", "")

                if on_progress:
                    await on_progress(100, "Transcription complete (HuggingFace).")

                return {
                    "text": text,
                    "segments": [],  # HF free tier doesn't return timestamps
                    "language": language,
                }

            elif response.status_code == 503:
                # Model is loading
                error_data = response.json()
                wait_time = error_data.get("estimated_time", RETRY_DELAY)
                if on_progress:
                    await on_progress(
                        (attempt / MAX_RETRIES) * 50,
                        f"Model is loading on HuggingFace... waiting {wait_time:.0f}s (attempt {attempt+1}/{MAX_RETRIES})",
                    )
                await asyncio.sleep(min(wait_time, 60))

            else:
                raise RuntimeError(
                    f"HuggingFace API error ({response.status_code}): {response.text}"
                )

    raise RuntimeError("HuggingFace API: max retries exceeded, model may still be loading.")


async def transcribe_audio_chunked(
    audio_chunks: list[Path],
    language: str = "hi",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """Transcribe multiple audio chunks via HF and merge results."""
    all_text = []

    for i, chunk_path in enumerate(audio_chunks):
        pct = (i / len(audio_chunks)) * 100
        if on_progress:
            await on_progress(pct, f"Transcribing chunk {i+1}/{len(audio_chunks)} via HuggingFace...")

        result = await transcribe_audio(chunk_path, language=language)
        all_text.append(result.get("text", ""))

    if on_progress:
        await on_progress(100, "All chunks transcribed via HuggingFace.")

    return {
        "text": " ".join(all_text),
        "segments": [],
        "language": language,
    }
