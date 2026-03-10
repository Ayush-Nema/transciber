"""Routes for serving video files."""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from config import VIDEOS_DIR

router = APIRouter(prefix="/api/video", tags=["video"])


@router.get("/{job_id}")
async def serve_video(job_id: str, request: Request):
    """Serve a downloaded video file with range request support."""
    # Find video file
    video_files = list(VIDEOS_DIR.glob(f"{job_id}.*"))
    if not video_files:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = video_files[0]
    file_size = video_path.stat().st_size
    content_type = _get_content_type(video_path.suffix)

    # Handle range requests for seeking
    range_header = request.headers.get("range")
    if range_header:
        start, end = _parse_range(range_header, file_size)
        chunk_size = end - start + 1

        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    read_size = min(remaining, 1024 * 1024)  # 1MB chunks
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iterfile(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    return FileResponse(
        video_path,
        media_type=content_type,
        headers={"Accept-Ranges": "bytes"},
    )


def _get_content_type(suffix: str) -> str:
    types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
    }
    return types.get(suffix.lower(), "video/mp4")


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse HTTP Range header."""
    try:
        ranges = range_header.replace("bytes=", "").split("-")
        start = int(ranges[0]) if ranges[0] else 0
        end = int(ranges[1]) if ranges[1] else file_size - 1
        end = min(end, file_size - 1)
        return start, end
    except (ValueError, IndexError):
        return 0, file_size - 1
