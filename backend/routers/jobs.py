"""API routes for transcription jobs."""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import async_session, get_db
from backend.models.job import ASRProvider, JobStatus, TranscriptionJob
from backend.services.sse_manager import sse_manager
from backend.services.transcription_orchestrator import run_download_only_pipeline, run_transcription_pipeline
from backend.services.video_service import detect_platform, fetch_video_info

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Request / Response Schemas ──


class CreateJobRequest(BaseModel):
    url: str
    asr_provider: str = Field(default="openai", pattern="^(openai|docker)$")
    language: str = Field(default="auto", max_length=10)
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, ge=0)
    split_duration: int | None = Field(default=None, ge=60, description="Split duration in seconds (min 60)")
    context: str | None = Field(default=None, max_length=1000, description="Context hint for ASR and LLM")
    llm_cleanup: bool = Field(default=True, description="Run LLM post-correction on transcription")
    preview_job_id: str | None = Field(
        default=None, description="If provided, reuse the video already downloaded by this preview job."
    )


class DownloadJobRequest(BaseModel):
    url: str


class JobResponse(BaseModel):
    id: str
    url: str
    platform: str
    asr_provider: str
    status: str
    progress: float
    progress_message: str
    title: str | None = None
    duration: float | None = None
    thumbnail_url: str | None = None
    video_path: str | None = None
    language: str
    start_time: float | None = None
    end_time: float | None = None
    split_duration: int | None = None
    transcription: str | None = None
    segments: list | None = None
    error_message: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class VideoInfoRequest(BaseModel):
    url: str


# ── Routes ──


@router.post("/video-info")
async def get_video_info(req: VideoInfoRequest):
    """Fetch video metadata without starting transcription."""
    try:
        platform = detect_platform(req.url)
        info = await fetch_video_info(req.url)
        return {
            "platform": platform.value,
            "title": info["title"],
            "duration": info["duration"],
            "thumbnail": info["thumbnail"],
            "description": info["description"],
            "uploader": info["uploader"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=JobResponse)
async def create_job(req: CreateJobRequest, db: AsyncSession = Depends(get_db)):
    """Create a new transcription job and start processing."""
    try:
        platform = detect_platform(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Prefer metadata + downloaded file from a preview job (Fetch Info) to avoid
    # re-running yt-dlp and re-downloading. Falls back to a fresh fetch otherwise.
    preview = await db.get(TranscriptionJob, req.preview_job_id) if req.preview_job_id else None
    reused_video_path = (
        preview.video_path if preview and preview.video_path and Path(preview.video_path).exists() else None
    )

    if preview and preview.title:
        title, duration, thumbnail = preview.title, preview.duration, preview.thumbnail_url
    else:
        try:
            info = await fetch_video_info(req.url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch video info: {e}")
        title, duration, thumbnail = info["title"], info["duration"], info["thumbnail"]

    job = TranscriptionJob(
        url=req.url,
        platform=platform,
        asr_provider=ASRProvider(req.asr_provider),
        language=req.language,
        title=title,
        duration=duration,
        thumbnail_url=thumbnail,
        video_path=reused_video_path,
        start_time=req.start_time,
        end_time=req.end_time,
        split_duration=req.split_duration,
        prompt=req.context,
        llm_cleanup=req.llm_cleanup,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Start pipeline in background
    async def _run_pipeline():
        async with async_session() as session:
            result = await session.get(TranscriptionJob, job.id)
            await run_transcription_pipeline(session, result)

    asyncio.create_task(_run_pipeline())

    return _job_to_response(job)


@router.post("/download", response_model=JobResponse)
async def create_download_job(req: DownloadJobRequest, db: AsyncSession = Depends(get_db)):
    """Create a job that only downloads the video (no transcription).

    Used by the "Fetch Info" flow so the video player and Download Video/MP3
    buttons can light up before the user commits to transcription.
    """
    try:
        platform = detect_platform(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        info = await fetch_video_info(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch video info: {e}")

    job = TranscriptionJob(
        url=req.url,
        platform=platform,
        title=info["title"],
        duration=info["duration"],
        thumbnail_url=info["thumbnail"],
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    async def _run_download():
        async with async_session() as session:
            result = await session.get(TranscriptionJob, job.id)
            await run_download_only_pipeline(session, result)

    asyncio.create_task(_run_download())

    return _job_to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get job status and results."""
    job = await db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint for streaming job progress."""
    job = await db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If already completed, return result immediately
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):

        async def _immediate():
            if job.status == JobStatus.COMPLETED:
                yield f'event: completed\ndata: {{"job_id": "{job_id}", "message": "Already completed"}}\n\n'
            else:
                yield f'event: error\ndata: {{"job_id": "{job_id}", "error": "{job.error_message}"}}\n\n'

        return StreamingResponse(_immediate(), media_type="text/event-stream")

    return StreamingResponse(
        sse_manager.event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _job_to_response(job: TranscriptionJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        url=job.url,
        platform=job.platform.value,
        asr_provider=job.asr_provider.value,
        status=job.status.value,
        progress=job.progress,
        progress_message=job.progress_message,
        title=job.title,
        duration=job.duration,
        thumbnail_url=job.thumbnail_url,
        video_path=job.video_path,
        language=job.language,
        start_time=job.start_time,
        end_time=job.end_time,
        split_duration=job.split_duration,
        transcription=job.transcription,
        segments=job.segments if isinstance(job.segments, list) else None,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )
