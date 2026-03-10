import asyncio
import re
import logging
from pathlib import Path
from typing import Callable, Awaitable

import yt_dlp

from config import VIDEOS_DIR, AUDIO_DIR
from models.job import Platform

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> Platform:
    """Detect platform from URL."""
    url_lower = url.lower()
    if any(d in url_lower for d in ["youtube.com", "youtu.be", "youtube.com/shorts"]):
        return Platform.YOUTUBE
    elif any(d in url_lower for d in ["instagram.com", "instagr.am"]):
        return Platform.INSTAGRAM
    elif any(d in url_lower for d in ["facebook.com", "fb.watch", "fb.com"]):
        return Platform.FACEBOOK
    raise ValueError(f"Unsupported URL: {url}. Supported: YouTube, Instagram, Facebook.")


async def fetch_video_info(url: str) -> dict:
    """Fetch video metadata without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = await asyncio.to_thread(_extract)
    return {
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "thumbnail": info.get("thumbnail", ""),
        "description": info.get("description", ""),
        "uploader": info.get("uploader", ""),
        "webpage_url": info.get("webpage_url", url),
    }


async def download_video(
    url: str,
    job_id: str,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> Path:
    """Download video and return file path."""
    output_template = str(VIDEOS_DIR / f"{job_id}.%(ext)s")

    progress_state = {"last_pct": 0.0}

    def _progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = (downloaded / total) * 100
                progress_state["last_pct"] = pct

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
        "socket_timeout": 30,
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    # Run download in thread with periodic progress callback
    task = asyncio.get_event_loop().run_in_executor(None, _download)

    while not task.done():
        if on_progress:
            await on_progress(
                progress_state["last_pct"],
                f"Downloading video... {progress_state['last_pct']:.0f}%",
            )
        await asyncio.sleep(1)

    await task  # Raise any exceptions

    # Find downloaded file
    video_files = list(VIDEOS_DIR.glob(f"{job_id}.*"))
    if not video_files:
        raise FileNotFoundError(f"Downloaded video not found for job {job_id}")

    return video_files[0]


async def extract_audio(
    video_path: Path,
    job_id: str,
    start_time: float | None = None,
    end_time: float | None = None,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> Path:
    """Extract audio from video using ffmpeg."""
    audio_path = AUDIO_DIR / f"{job_id}.wav"

    cmd = ["ffmpeg", "-y", "-i", str(video_path)]

    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])
    if end_time is not None:
        cmd.extend(["-to", str(end_time)])

    cmd.extend([
        "-vn",                  # No video
        "-acodec", "pcm_s16le", # WAV format
        "-ar", "16000",         # 16kHz sample rate (required by Whisper)
        "-ac", "1",             # Mono
        str(audio_path),
    ])

    if on_progress:
        await on_progress(0, "Extracting audio from video...")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

    if on_progress:
        await on_progress(100, "Audio extraction complete.")

    return audio_path


async def preprocess_audio(
    audio_path: Path,
    job_id: str,
    on_progress: Callable[[float, str], Awaitable[None]] | None = None,
) -> Path:
    """
    Preprocess audio for better transcription accuracy:
    - High-pass filter at 80Hz to remove low-frequency rumble
    - Noise gate to suppress background noise
    - Volume normalization (loudnorm) for consistent levels
    """
    processed_path = AUDIO_DIR / f"{job_id}_processed.wav"

    if on_progress:
        await on_progress(0, "Preprocessing audio (noise reduction + normalization)...")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", ",".join([
            "highpass=f=80",           # Remove rumble below 80Hz
            "afftdn=nf=-25",           # FFT-based noise reduction
            "loudnorm=I=-16:TP=-1.5",  # EBU R128 loudness normalization
        ]),
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(processed_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.warning(f"Audio preprocessing failed, using original: {stderr.decode()[:200]}")
        return audio_path  # Fallback to unprocessed audio

    if on_progress:
        await on_progress(100, "Audio preprocessing complete.")

    return processed_path


async def split_audio(
    audio_path: Path,
    job_id: str,
    split_duration_seconds: int,
) -> list[Path]:
    """Split an audio file into chunks of given duration."""
    # Get total duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    process = await asyncio.create_subprocess_exec(
        *probe_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    total_duration = float(stdout.decode().strip())

    chunks = []
    start = 0.0
    idx = 0

    while start < total_duration:
        chunk_path = AUDIO_DIR / f"{job_id}_chunk_{idx:03d}.wav"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-ss", str(start),
            "-t", str(split_duration_seconds),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(chunk_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        chunks.append(chunk_path)
        start += split_duration_seconds
        idx += 1

    return chunks
