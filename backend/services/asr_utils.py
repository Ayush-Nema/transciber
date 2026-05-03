"""Shared utilities for ASR providers."""

from pathlib import Path
from typing import Awaitable, Callable


async def transcribe_chunked(
    transcribe_fn: Callable[..., Awaitable[dict]],
    audio_chunks: list[Path],
    provider_label: str,
    language: str = "auto",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
    **transcribe_kwargs,
) -> dict:
    """
    Generic chunked transcription: calls transcribe_fn for each chunk,
    merges text and time-offset segments.
    """
    all_text = []
    all_segments = []
    time_offset = 0.0

    for i, chunk_path in enumerate(audio_chunks):
        pct = (i / len(audio_chunks)) * 100
        if on_progress:
            await on_progress(pct, f"Transcribing chunk {i + 1}/{len(audio_chunks)} via {provider_label}...")

        result = await transcribe_fn(chunk_path, language=language, **transcribe_kwargs)
        all_text.append(result.get("text", ""))

        for seg in result.get("segments", []):
            all_segments.append(
                {
                    "start": seg["start"] + time_offset,
                    "end": seg["end"] + time_offset,
                    "text": seg["text"],
                }
            )

        if result.get("segments"):
            time_offset += result["segments"][-1]["end"]

    if on_progress:
        await on_progress(100, f"All chunks transcribed via {provider_label}.")

    return {
        "text": " ".join(all_text),
        "segments": all_segments,
        "language": language,
    }
