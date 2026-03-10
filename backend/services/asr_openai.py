"""ASR client using OpenAI Transcription API."""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable

import httpx

from config import OPENAI_API_KEY, OPENAI_TRANSCRIPTION_MODEL

logger = logging.getLogger(__name__)

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
TIMEOUT = httpx.Timeout(timeout=600.0, connect=30.0)
MAX_FILE_SIZE_MB = 25  # OpenAI limit


async def transcribe_audio(
    audio_path: Path,
    language: str = "hi",
    prompt: str | None = None,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """
    Send audio to OpenAI Transcription API.
    Returns: {"text": str, "segments": [{"start": float, "end": float, "text": str}], "language": str}

    Model behavior:
    - whisper-1: supports verbose_json with segment timestamps
    - gpt-4o-mini-transcribe / gpt-4o-transcribe: only json/text, better accuracy (especially Hindi),
      but no segment-level timestamps from the API
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise RuntimeError(
            f"Audio file is {file_size_mb:.1f}MB — exceeds OpenAI's {MAX_FILE_SIZE_MB}MB limit. "
            "Use the split feature to break it into smaller chunks."
        )

    model = OPENAI_TRANSCRIPTION_MODEL
    is_whisper = model == "whisper-1"

    if on_progress:
        label = "Whisper" if is_whisper else model
        await on_progress(0, f"Sending audio to OpenAI {label}...")

    lang = language if language and language != "auto" else None

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}

            if is_whisper:
                # whisper-1 supports verbose_json with timestamps
                data = {
                    "model": model,
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                }
            else:
                # gpt-4o-mini-transcribe / gpt-4o-transcribe: json only
                data = {
                    "model": model,
                    "response_format": "json",
                }

            if lang:
                data["language"] = lang
            if prompt:
                data["prompt"] = prompt

            response = await client.post(
                OPENAI_TRANSCRIPTION_URL,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            )

    if response.status_code != 200:
        raise RuntimeError(f"OpenAI API error ({response.status_code}): {response.text}")

    result = response.json()

    # Parse segments (only available with whisper-1 verbose_json)
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        })

    detected_lang = result.get("language", language)
    full_text = result.get("text", "")

    if on_progress:
        label = "Whisper" if is_whisper else model
        await on_progress(100, f"Transcription complete (OpenAI {label}).")

    logger.info(
        f"OpenAI transcription done (model={model}): "
        f"{len(segments)} segments, language={detected_lang}"
    )

    return {
        "text": full_text,
        "segments": segments,
        "language": detected_lang,
    }


async def transcribe_audio_chunked(
    audio_chunks: list[Path],
    language: str = "hi",
    prompt: str | None = None,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """Transcribe multiple audio chunks via OpenAI and merge results."""
    all_text = []
    all_segments = []
    time_offset = 0.0

    for i, chunk_path in enumerate(audio_chunks):
        pct = (i / len(audio_chunks)) * 100
        if on_progress:
            await on_progress(pct, f"Transcribing chunk {i+1}/{len(audio_chunks)} via OpenAI...")

        result = await transcribe_audio(chunk_path, language=language, prompt=prompt)
        all_text.append(result.get("text", ""))

        for seg in result.get("segments", []):
            all_segments.append({
                "start": seg["start"] + time_offset,
                "end": seg["end"] + time_offset,
                "text": seg["text"],
            })

        # Advance offset by last segment end
        if result.get("segments"):
            time_offset += result["segments"][-1]["end"]

    if on_progress:
        await on_progress(100, "All chunks transcribed via OpenAI.")

    return {
        "text": " ".join(all_text),
        "segments": all_segments,
        "language": language,
    }
