"""LLM post-correction of transcription using GPT-4o-mini."""
import logging
from typing import Callable, Awaitable

import httpx

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = httpx.Timeout(timeout=120.0, connect=30.0)

CORRECTION_SYSTEM_PROMPT = """\
You are a transcription post-processor. Your job is to clean up and correct \
raw speech-to-text output. The transcription is primarily in Hindi (Devanagari) \
but may contain code-switched Hindi-English (Hinglish) segments.

Rules:
1. Fix obvious transcription errors, misheard words, and garbled text.
2. Correct Hindi spellings and fix broken Devanagari sequences.
3. For code-switched Hindi-English, ensure English words are spelled correctly \
   while keeping the natural mixed-language flow.
4. Add proper punctuation: full stops (।), commas, and question marks.
5. Fix sentence boundaries — split run-on text into natural sentences.
6. Do NOT translate — keep the original language as-is.
7. Do NOT add, remove, or rephrase content — only correct errors.
8. Preserve the meaning exactly. When unsure, keep the original.
9. Return ONLY the corrected text, nothing else."""


async def postprocess_transcription(
    raw_text: str,
    language: str = "hi",
    context_hint: str = "",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> str:
    """
    Clean up raw transcription text using GPT-4o-mini.
    Returns corrected text.
    """
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping LLM post-processing.")
        return raw_text

    if not raw_text or len(raw_text.strip()) < 20:
        return raw_text

    if on_progress:
        await on_progress(0, "Cleaning up transcription with LLM...")

    user_msg = f"Correct this {language} transcription:\n\n{raw_text}"
    if context_hint:
        user_msg = f"Context: {context_hint}\n\n{user_msg}"

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,  # Low temp for faithful correction
        "max_tokens": 16000,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            OPENAI_CHAT_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )

    if response.status_code != 200:
        logger.error(f"LLM post-processing failed ({response.status_code}): {response.text}")
        return raw_text  # Fallback to raw text on error

    result = response.json()
    corrected = result["choices"][0]["message"]["content"].strip()

    if on_progress:
        await on_progress(100, "Transcription cleaned up.")

    logger.info(f"LLM post-processing done: {len(raw_text)} -> {len(corrected)} chars")
    return corrected


async def postprocess_segments(
    segments: list[dict],
    language: str = "hi",
    context_hint: str = "",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> list[dict]:
    """
    Clean up segment-level text using GPT-4o-mini.
    Processes in batches to stay within token limits.
    """
    if not OPENAI_API_KEY or not segments:
        return segments

    if on_progress:
        await on_progress(0, "Cleaning up segment text with LLM...")

    # Batch segments (roughly 50 at a time to fit in context)
    BATCH_SIZE = 50
    corrected_segments = []

    for batch_start in range(0, len(segments), BATCH_SIZE):
        batch = segments[batch_start:batch_start + BATCH_SIZE]
        pct = (batch_start / len(segments)) * 100

        if on_progress:
            await on_progress(pct, f"Cleaning segments {batch_start+1}-{batch_start+len(batch)}...")

        # Build numbered text for the batch
        numbered_lines = []
        for i, seg in enumerate(batch):
            numbered_lines.append(f"{i+1}. {seg['text']}")
        batch_text = "\n".join(numbered_lines)

        user_msg = (
            f"Correct each line of this {language} transcription. "
            f"Keep the numbering. Return ONLY the corrected numbered lines:\n\n{batch_text}"
        )
        if context_hint:
            user_msg = f"Context: {context_hint}\n\n{user_msg}"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": CORRECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
            "max_tokens": 8000,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    OPENAI_CHAT_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code == 200:
                result = response.json()
                corrected_text = result["choices"][0]["message"]["content"].strip()

                # Parse numbered lines back
                corrected_lines = []
                for line in corrected_text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Strip leading number + dot/parenthesis
                    import re
                    cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
                    if cleaned:
                        corrected_lines.append(cleaned)

                # Map back to segments
                for i, seg in enumerate(batch):
                    new_seg = {**seg}
                    if i < len(corrected_lines):
                        new_seg["text"] = corrected_lines[i]
                    corrected_segments.append(new_seg)
            else:
                # On error, keep originals
                corrected_segments.extend(batch)

        except Exception as e:
            logger.error(f"LLM segment correction failed: {e}")
            corrected_segments.extend(batch)

    if on_progress:
        await on_progress(100, "Segment cleanup done.")

    return corrected_segments
