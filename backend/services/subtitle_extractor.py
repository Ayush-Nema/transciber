"""
Extract existing subtitles/captions from YouTube videos using yt-dlp.

This avoids running ASR altogether when YouTube already has subtitles,
giving instant results with good accuracy (especially for popular languages).
Supports both manual captions and YouTube's auto-generated captions.
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Callable, Awaitable

import yt_dlp

from config import DATA_DIR

logger = logging.getLogger(__name__)

SUBS_DIR = DATA_DIR / "subs"
SUBS_DIR.mkdir(parents=True, exist_ok=True)


def _parse_vtt_timestamp(ts: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 3:
        h, m, rest = parts
        s = rest.replace(",", ".")
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, rest = parts
        s = rest.replace(",", ".")
        return int(m) * 60 + float(s)
    return 0.0


def _clean_vtt_text(text: str) -> str:
    """Strip VTT formatting tags like <c>, </c>, <00:00:00.000>, etc."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip()
    return text


def _parse_vtt_cues(vtt_text: str) -> list[dict]:
    """
    Parse raw VTT cues from the file.
    Returns: [{"start": float, "end": float, "text": str}, ...]
    """
    cues = []
    cue_pattern = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})"
    )

    lines = vtt_text.split("\n")
    i = 0
    while i < len(lines):
        match = cue_pattern.match(lines[i].strip())
        if match:
            start = _parse_vtt_timestamp(match.group(1))
            end = _parse_vtt_timestamp(match.group(2))
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and not cue_pattern.match(lines[i].strip()):
                cleaned = _clean_vtt_text(lines[i])
                if cleaned:
                    text_lines.append(cleaned)
                i += 1

            text = " ".join(text_lines).strip()
            if text:
                cues.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": text,
                })
        else:
            i += 1

    return cues


def _merge_rolling_cues(cues: list[dict], gap_threshold: float = 2.0) -> list[dict]:
    """
    Merge YouTube's rolling-window VTT cues into clean, non-overlapping segments.

    YouTube auto-captions use a rolling style where each cue repeats text from
    the previous cue plus new words:
        00:01 --> 00:03  "hello world"
        00:02 --> 00:05  "hello world how are"
        00:04 --> 00:07  "how are you today"

    This function:
    1. Extracts only the NEW text from each cue (removing overlap with previous)
    2. Groups consecutive new-text fragments into sentence-like segments
       (merging when the gap between cues is small)
    3. Returns clean segments with proper start/end times
    """
    if not cues:
        return []

    # Step 1: Extract only new text from each cue
    fragments = []  # (start, end, new_text)
    prev_text = ""

    for cue in cues:
        cur_text = cue["text"]

        # Find the new portion by checking if current text starts with or contains prev text
        new_text = cur_text
        if prev_text and cur_text != prev_text:
            # Check if current text contains the previous text as a prefix
            if cur_text.startswith(prev_text):
                new_text = cur_text[len(prev_text):].strip()
            else:
                # Try word-level overlap detection:
                # Find the longest suffix of prev_text that is a prefix of cur_text
                prev_words = prev_text.split()
                cur_words = cur_text.split()

                best_overlap = 0
                for overlap_len in range(1, min(len(prev_words), len(cur_words)) + 1):
                    if prev_words[-overlap_len:] == cur_words[:overlap_len]:
                        best_overlap = overlap_len

                if best_overlap > 0:
                    new_words = cur_words[best_overlap:]
                    new_text = " ".join(new_words) if new_words else ""
                # else: no overlap found, keep full text as new

        if new_text:
            fragments.append({
                "start": cue["start"],
                "end": cue["end"],
                "text": new_text,
            })

        prev_text = cur_text

    if not fragments:
        return cues  # fallback to raw cues

    # Step 2: Merge fragments into sentence-like segments
    # Group fragments that are close together (within gap_threshold seconds)
    merged = []
    current = {
        "start": fragments[0]["start"],
        "end": fragments[0]["end"],
        "texts": [fragments[0]["text"]],
    }

    for frag in fragments[1:]:
        gap = frag["start"] - current["end"]
        accumulated_text = " ".join(current["texts"])

        # Merge if gap is small AND accumulated text isn't too long yet
        if gap <= gap_threshold and len(accumulated_text) < 200:
            current["end"] = frag["end"]
            current["texts"].append(frag["text"])
        else:
            merged.append({
                "start": current["start"],
                "end": current["end"],
                "text": " ".join(current["texts"]).strip(),
            })
            current = {
                "start": frag["start"],
                "end": frag["end"],
                "texts": [frag["text"]],
            }

    # Don't forget the last segment
    merged.append({
        "start": current["start"],
        "end": current["end"],
        "text": " ".join(current["texts"]).strip(),
    })

    # Filter out empty segments
    return [seg for seg in merged if seg["text"]]


def _parse_vtt_content(vtt_text: str) -> list[dict]:
    """
    Parse VTT subtitle content into clean, deduplicated segments.
    Handles YouTube's rolling-window auto-caption format.
    Returns: [{"start": float, "end": float, "text": str}, ...]
    """
    cues = _parse_vtt_cues(vtt_text)
    if not cues:
        return []

    # Check if this looks like YouTube rolling-window format
    # (many short, overlapping cues with repeated text)
    is_rolling = False
    if len(cues) > 3:
        overlap_count = 0
        for i in range(1, min(len(cues), 20)):
            prev_words = set(cues[i - 1]["text"].split())
            cur_words = set(cues[i]["text"].split())
            if prev_words and cur_words:
                overlap_ratio = len(prev_words & cur_words) / max(len(prev_words), len(cur_words))
                if overlap_ratio > 0.4:
                    overlap_count += 1
        is_rolling = overlap_count > len(cues[:20]) * 0.4

    if is_rolling:
        logger.info(f"Detected YouTube rolling-window VTT format ({len(cues)} raw cues)")
        return _merge_rolling_cues(cues)
    else:
        # Standard VTT — just deduplicate exact matches
        deduped = []
        seen = set()
        for seg in cues:
            key = (seg["start"], seg["text"])
            if key not in seen:
                seen.add(key)
                deduped.append(seg)
        return deduped


async def check_subtitles_available(url: str) -> dict | None:
    """
    Check if subtitles are available for a video URL.
    Returns subtitle info dict or None if no subtitles found.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    def _check():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get("subtitles", {})
            auto_subs = info.get("automatic_captions", {})
            return {
                "manual_subtitles": subs,
                "auto_captions": auto_subs,
                "video_id": info.get("id", ""),
            }

    return await asyncio.to_thread(_check)


async def extract_subtitles(
    url: str,
    job_id: str,
    language: str = "hi",
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> dict | None:
    """
    Attempt to extract existing subtitles from a YouTube video.

    Priority:
    1. Manual subtitles in requested language
    2. Auto-generated captions in requested language
    3. Manual subtitles in English (as fallback)
    4. Auto-generated captions in English (as fallback)

    Returns: {"text": str, "segments": [...], "language": str, "source": str} or None
    """
    if on_progress:
        await on_progress(0, "Checking for existing subtitles...")

    try:
        sub_info = await check_subtitles_available(url)
    except Exception as e:
        logger.warning(f"Subtitle check failed: {e}")
        return None

    if not sub_info:
        return None

    manual = sub_info["manual_subtitles"]
    auto = sub_info["auto_captions"]

    # Determine which subtitle track to use (priority order)
    selected_lang = None
    source_type = None
    sub_list = None

    # Map common language codes (yt-dlp uses different codes sometimes)
    lang_variants = [language]
    if language == "hi":
        lang_variants.extend(["hi", "hin"])
    elif language == "en":
        lang_variants.extend(["en", "en-US", "en-GB", "eng"])

    for lang_code in lang_variants:
        if lang_code in manual:
            selected_lang = lang_code
            source_type = "manual"
            sub_list = manual[lang_code]
            break

    if not selected_lang:
        for lang_code in lang_variants:
            if lang_code in auto:
                selected_lang = lang_code
                source_type = "auto_caption"
                sub_list = auto[lang_code]
                break

    # Fallback to English if requested language not found
    if not selected_lang and language != "en":
        for lang_code in ["en", "en-US", "en-GB"]:
            if lang_code in manual:
                selected_lang = lang_code
                source_type = "manual"
                sub_list = manual[lang_code]
                break
            if lang_code in auto:
                selected_lang = lang_code
                source_type = "auto_caption"
                sub_list = auto[lang_code]
                break

    if not selected_lang or not sub_list:
        if on_progress:
            await on_progress(100, "No subtitles found, will use ASR.")
        return None

    if on_progress:
        await on_progress(30, f"Found {source_type} subtitles ({selected_lang}), downloading...")

    # Download the subtitle file using yt-dlp
    sub_path = SUBS_DIR / f"{job_id}.{selected_lang}.vtt"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": source_type == "manual",
        "writeautomaticsub": source_type == "auto_caption",
        "subtitleslangs": [selected_lang],
        "subtitlesformat": "vtt",
        "outtmpl": str(SUBS_DIR / f"{job_id}"),
    }

    def _download_subs():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    try:
        await asyncio.to_thread(_download_subs)
    except Exception as e:
        logger.warning(f"Subtitle download failed: {e}")
        if on_progress:
            await on_progress(100, "Subtitle download failed, will use ASR.")
        return None

    # Find the downloaded subtitle file
    sub_files = list(SUBS_DIR.glob(f"{job_id}*.vtt"))
    if not sub_files:
        if on_progress:
            await on_progress(100, "Subtitle file not found after download, will use ASR.")
        return None

    sub_path = sub_files[0]

    if on_progress:
        await on_progress(60, "Parsing subtitle file...")

    # Read and parse the VTT file
    vtt_content = sub_path.read_text(encoding="utf-8")
    segments = _parse_vtt_content(vtt_content)

    if not segments:
        if on_progress:
            await on_progress(100, "Subtitle file was empty, will use ASR.")
        return None

    # Build full text from segments
    full_text = " ".join(seg["text"] for seg in segments)

    if on_progress:
        source_label = "manual subtitles" if source_type == "manual" else "auto-captions"
        await on_progress(
            100,
            f"Extracted {len(segments)} segments from YouTube {source_label} ({selected_lang})."
        )

    logger.info(
        f"Subtitle extraction done for job {job_id}: "
        f"{len(segments)} segments from {source_type} ({selected_lang})"
    )

    return {
        "text": full_text,
        "segments": segments,
        "language": selected_lang,
        "source": source_type,  # "manual" or "auto_caption"
    }
