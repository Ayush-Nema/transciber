"""Generate structured mind-map data from transcription using GPT-4o-mini."""
import json
import re
import logging
from collections import Counter
from typing import Callable, Awaitable

import httpx

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = httpx.Timeout(timeout=120.0, connect=30.0)

MINDMAP_SYSTEM_PROMPT = """\
You are a content analyst. Given a video transcription, extract a structured \
mind-map of the content. Return a JSON object with this exact structure:

{
  "title": "Main topic of the video",
  "themes": [
    {
      "label": "Theme/topic name",
      "points": [
        {
          "text": "Key point or argument",
          "detail": "Brief supporting detail or example (1 sentence, optional)"
        }
      ]
    }
  ]
}

Rules:
1. Extract 3-6 main themes that capture the actual topics discussed.
2. Each theme should have 2-5 key points.
3. Theme labels should be concise (2-5 words).
4. Key points should be clear, factual statements from the content.
5. Details are optional — include only when there's a specific example, \
   statistic, or quote worth noting.
6. Keep the original language of the content. If the video is in Hindi, \
   write themes and points in Hindi. If mixed Hindi-English (Hinglish), \
   keep that natural mix.
7. Do NOT invent information — only extract what was actually discussed.
8. Return ONLY valid JSON, no markdown fences, no explanation."""


async def generate_mindmap_llm(
    text: str,
    title: str = "Transcription",
    language: str = "hi",
    context_hint: str = "",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> str:
    """
    Generate mind-map JSON using GPT-4o-mini.
    Returns JSON string of the mind-map structure.
    Falls back to simple extraction on error.
    """
    if not OPENAI_API_KEY or not text or len(text.strip()) < 50:
        return _fallback_mindmap(text, title)

    if on_progress:
        await on_progress(0, "Generating mind-map with AI...")

    # Truncate text if too long (keep first ~12k chars to fit in context)
    truncated = text[:12000] if len(text) > 12000 else text

    user_msg = f"Video title: {title}\n"
    if context_hint:
        user_msg += f"Context: {context_hint}\n"
    user_msg += f"Language: {language}\n\nTranscription:\n{truncated}"

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": MINDMAP_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
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

        if response.status_code != 200:
            logger.error(f"Mind-map generation failed ({response.status_code}): {response.text}")
            return _fallback_mindmap(text, title)

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        # Validate it's proper JSON
        parsed = json.loads(content)

        # Ensure required structure exists
        if "themes" not in parsed:
            parsed = {"title": title, "themes": []}
        if "title" not in parsed:
            parsed["title"] = title

        if on_progress:
            theme_count = len(parsed.get("themes", []))
            await on_progress(100, f"Mind-map generated ({theme_count} themes).")

        logger.info(f"LLM mind-map generated: {len(parsed.get('themes', []))} themes")
        return json.dumps(parsed, ensure_ascii=False)

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Mind-map JSON parse error: {e}")
        return _fallback_mindmap(text, title)
    except Exception as e:
        logger.error(f"Mind-map generation error: {e}")
        return _fallback_mindmap(text, title)


def _fallback_mindmap(text: str, title: str) -> str:
    """Simple fallback when LLM is unavailable — extract basic structure."""
    STOP_WORDS = {
        "है", "हैं", "था", "थे", "थी", "को", "का", "के", "की", "में", "पर", "से",
        "ने", "और", "या", "भी", "तो", "ही", "एक", "यह", "वह", "इस", "उस", "जो",
        "the", "is", "are", "was", "were", "a", "an", "and", "or", "but", "in",
        "on", "at", "to", "for", "of", "with", "by", "from", "this", "that",
        "it", "he", "she", "we", "they", "you", "i", "not", "so", "if", "as",
    }

    if not text or len(text.strip()) < 20:
        return json.dumps({"title": title, "themes": []}, ensure_ascii=False)

    words = re.findall(r'\b[\w\u0900-\u097F]{3,}\b', text.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    top_words = [w for w, _ in Counter(filtered).most_common(12)]

    themes = []
    for i in range(0, min(len(top_words), 9), 3):
        group = top_words[i:i + 3]
        if group:
            themes.append({
                "label": group[0].capitalize(),
                "points": [{"text": w, "detail": None} for w in group[1:]],
            })

    return json.dumps({"title": title, "themes": themes}, ensure_ascii=False)


# Functions used by orchestrator
async def generate_mindmap_from_segments(
    segments: list[dict],
    title: str = "Transcription",
    language: str = "hi",
    context_hint: str = "",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> str:
    """Generate mind-map from timestamped segments."""
    text = " ".join(seg.get("text", "") for seg in segments)
    return await generate_mindmap_llm(text, title, language, context_hint, on_progress)


async def generate_mindmap_from_text(
    text: str,
    title: str = "Transcription",
    language: str = "hi",
    context_hint: str = "",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> str:
    """Generate mind-map from plain text."""
    return await generate_mindmap_llm(text, title, language, context_hint, on_progress)
