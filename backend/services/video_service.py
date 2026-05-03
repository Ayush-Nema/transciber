import asyncio
import json
import os
from pathlib import Path
from typing import Awaitable, Callable

import yt_dlp
from loguru import logger

from backend.config import AUDIO_DIR, VIDEOS_DIR
from backend.models.job import Platform

COOKIES_BROWSER = os.environ.get("COOKIES_BROWSER", "")  # e.g. "chrome", "firefox", "brave"
COOKIES_FILE = os.environ.get("COOKIES_FILE", "")  # path to Netscape cookies.txt (for Docker)


def _apply_cookies(opts: dict) -> None:
    """Add cookie config to yt-dlp options."""
    if COOKIES_BROWSER:
        opts["cookiesfrombrowser"] = (COOKIES_BROWSER,)
    elif COOKIES_FILE:
        opts["cookiefile"] = COOKIES_FILE


def _parse_loudnorm_stats(ffmpeg_stderr: str) -> dict | None:
    """Extract measured loudness values from ffmpeg loudnorm print_format=json output."""
    # ffmpeg prints the JSON block in stderr after the loudnorm analysis pass
    try:
        # Find the JSON block between the last { and }
        start = ffmpeg_stderr.rfind("{")
        end = ffmpeg_stderr.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        raw = ffmpeg_stderr[start:end]
        data = json.loads(raw)
        # Validate expected keys exist
        required = ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]
        if all(k in data for k in required):
            return data
        return None
    except (json.JSONDecodeError, ValueError):
        return None


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
    _apply_cookies(ydl_opts)

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
    expected_duration: float | None = None,
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
        # Instagram often serves incomplete content without proper headers/cookies
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        },
        "extractor_args": {"instagram": {"skip": ["dash"]}},
    }

    _apply_cookies(ydl_opts)

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

    downloaded_path = video_files[0]

    # Verify downloaded duration matches expected
    actual_duration = await probe_duration(downloaded_path)
    if actual_duration:
        logger.info(f"Downloaded video duration: {actual_duration:.1f}s for job {job_id}")
        if expected_duration and actual_duration < expected_duration * 0.8:
            logger.warning(
                f"Downloaded video ({actual_duration:.1f}s) is significantly shorter than "
                f"expected ({expected_duration:.1f}s) for job {job_id}. "
                "Instagram may have served a truncated version."
            )

    return downloaded_path


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

    cmd.extend(
        [
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",  # WAV format
            "-ar",
            "16000",  # 16kHz sample rate (required by Whisper)
            "-ac",
            "1",  # Mono
            str(audio_path),
        ]
    )

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
    Preprocess audio for better transcription accuracy.

    Two-pass loudnorm to avoid the single-pass startup ramp that silences the
    first several seconds.  We intentionally skip FFT-based noise reduction
    (afftdn) because it builds a noise profile from the first few seconds of
    audio — when those seconds contain speech (common in short-form content
    like Instagram reels), it suppresses the opening dialogue.
    """
    processed_path = AUDIO_DIR / f"{job_id}_processed.wav"

    if on_progress:
        await on_progress(0, "Preprocessing audio (normalization)...")

    # ── Pass 1: measure loudness stats ──
    measure_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-af",
        "highpass=f=80,loudnorm=I=-16:TP=-1.5:print_format=json",
        "-f",
        "null",
        "-",
    ]

    proc1 = await asyncio.create_subprocess_exec(
        *measure_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr1 = await proc1.communicate()
    stderr_text = stderr1.decode()

    # Parse measured loudness values from ffmpeg output
    measured = _parse_loudnorm_stats(stderr_text)

    if measured:
        # ── Pass 2: apply measured values (linear mode — no startup ramp) ──
        loudnorm_filter = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            f":linear=true"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-af",
            f"highpass=f=80,{loudnorm_filter}",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(processed_path),
        ]
    else:
        # Fallback: just highpass, skip loudnorm entirely
        logger.warning("Could not parse loudnorm stats, using highpass only")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-af",
            "highpass=f=80",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
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


async def convert_to_mp3(video_path: Path, job_id: str) -> Path:
    """Convert video to MP3 audio file using ffmpeg."""
    mp3_path = AUDIO_DIR / f"{job_id}.mp3"

    if mp3_path.exists():
        return mp3_path

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ab",
        "192k",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(mp3_path),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"MP3 conversion failed: {stderr.decode()[:300]}")

    logger.info(f"Converted to MP3: {mp3_path} ({mp3_path.stat().st_size / (1024 * 1024):.1f}MB)")
    return mp3_path


async def probe_duration(file_path: Path) -> float | None:
    """Get duration of an audio/video file in seconds."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except Exception:
        return None


async def split_audio(
    audio_path: Path,
    job_id: str,
    split_duration_seconds: int,
) -> list[Path]:
    """Split an audio file into chunks of given duration."""
    total_duration = await probe_duration(audio_path)
    if not total_duration:
        raise RuntimeError(f"Could not determine duration for {audio_path}")

    chunks = []
    start = 0.0
    idx = 0

    while start < total_duration:
        chunk_path = AUDIO_DIR / f"{job_id}_chunk_{idx:03d}.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_path),
            "-ss",
            str(start),
            "-t",
            str(split_duration_seconds),
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
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
