"""ASR client using OpenAI Transcription API."""

import asyncio
import random
from pathlib import Path
from typing import Awaitable, Callable

import httpx
from loguru import logger

from backend.config import OPENAI_API_KEY, OPENAI_TRANSCRIPTION_MODEL
from backend.services.asr_utils import transcribe_chunked

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"
TIMEOUT = httpx.Timeout(timeout=600.0, connect=30.0)
MAX_FILE_SIZE_MB = 25  # OpenAI limit

# Retry config for transient upstream failures (Cloudflare 520/5xx, 429 rate limits, network blips)
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
MAX_ATTEMPTS = 4
BASE_RETRY_DELAY = 2.0  # seconds; doubles each attempt


async def transcribe_audio(
    audio_path: Path,
    language: str = "auto",
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

    # Read once so we can retry without re-opening the file.
    audio_bytes = audio_path.read_bytes()
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    response = await _post_with_retries(
        audio_path.name,
        audio_bytes,
        data,
        headers,
        on_progress=on_progress,
    )

    if response.status_code != 200:
        # Truncate body — error pages (e.g. Cloudflare 520) can be huge HTML blobs
        body = response.text[:500]
        raise RuntimeError(f"OpenAI API error ({response.status_code}): {body}")

    result = response.json()

    # Parse segments (only available with whisper-1 verbose_json)
    segments = []
    for seg in result.get("segments", []):
        segments.append(
            {
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
            }
        )

    detected_lang = result.get("language", language)
    full_text = result.get("text", "")

    if on_progress:
        label = "Whisper" if is_whisper else model
        await on_progress(100, f"Transcription complete (OpenAI {label}).")

    logger.info(f"OpenAI transcription done (model={model}): {len(segments)} segments, language={detected_lang}")

    return {
        "text": full_text,
        "segments": segments,
        "language": detected_lang,
    }


async def _post_with_retries(
    filename: str,
    audio_bytes: bytes,
    data: dict,
    headers: dict,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> httpx.Response:
    """POST to the OpenAI transcription endpoint, retrying transient failures.

    Retries on: connection/timeout errors, and HTTP 408/425/429/5xx (including
    Cloudflare 52x). Honors the ``Retry-After`` header when present. Returns the
    final ``httpx.Response`` — caller is responsible for checking ``status_code``.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            files = {"file": (filename, audio_bytes, "audio/wav")}
            try:
                response = await client.post(
                    OPENAI_TRANSCRIPTION_URL,
                    files=files,
                    data=data,
                    headers=headers,
                )
            except (httpx.TransportError, httpx.TimeoutException) as e:
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"OpenAI API network error after {MAX_ATTEMPTS} attempts: {e}") from e
                await _sleep_before_retry(attempt, None, on_progress, reason=f"network error ({type(e).__name__})")
                continue

            if response.status_code == 200 or response.status_code not in RETRY_STATUSES:
                return response
            if attempt == MAX_ATTEMPTS:
                return response

            await _sleep_before_retry(
                attempt,
                response.headers.get("Retry-After"),
                on_progress,
                reason=f"HTTP {response.status_code}",
            )

        # The loop above always either returns or raises before exiting.
        raise AssertionError("unreachable: _post_with_retries loop exhausted without return")


async def _sleep_before_retry(
    attempt: int,
    retry_after_header: str | None,
    on_progress: Callable[[float, str], Awaitable[None]] | None,
    reason: str,
) -> None:
    delay = BASE_RETRY_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
    if retry_after_header:
        try:
            delay = max(delay, float(retry_after_header))
        except ValueError:
            pass
    logger.warning(
        f"OpenAI transcription transient failure ({reason}); retrying in {delay:.1f}s "
        f"[attempt {attempt}/{MAX_ATTEMPTS}]"
    )
    if on_progress:
        await on_progress(
            0,
            f"OpenAI {reason}, retrying in {delay:.0f}s ({attempt}/{MAX_ATTEMPTS})...",
        )
    await asyncio.sleep(delay)


async def transcribe_audio_chunked(
    audio_chunks: list[Path],
    language: str = "auto",
    prompt: str | None = None,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict:
    """Transcribe multiple audio chunks via OpenAI and merge results."""
    kwargs = {"prompt": prompt} if prompt else {}
    return await transcribe_chunked(
        transcribe_audio,
        audio_chunks,
        "OpenAI",
        language=language,
        on_progress=on_progress,
        **kwargs,
    )
