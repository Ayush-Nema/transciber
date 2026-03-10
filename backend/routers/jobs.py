"""API routes for transcription jobs."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, async_session
from models.job import TranscriptionJob, JobStatus, ASRProvider, Platform
from services.video_service import detect_platform, fetch_video_info
from services.sse_manager import sse_manager
from services.transcription_orchestrator import run_transcription_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── Request / Response Schemas ──

class CreateJobRequest(BaseModel):
    url: str
    asr_provider: str = Field(default="openai", pattern="^(openai|docker|huggingface)$")
    language: str = Field(default="hi", max_length=10)
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, ge=0)
    split_duration: int | None = Field(default=None, ge=60, description="Split duration in seconds (min 60)")
    prompt: str | None = Field(default=None, max_length=1000, description="Context prompt for Whisper (e.g. expected vocabulary)")
    context_hint: str | None = Field(default=None, max_length=500, description="Topic hint for LLM post-correction")


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
    mindmap_mermaid: str | None = None
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

    # Fetch video info first
    try:
        info = await fetch_video_info(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch video info: {e}")

    job = TranscriptionJob(
        url=req.url,
        platform=platform,
        asr_provider=ASRProvider(req.asr_provider),
        language=req.language,
        title=info["title"],
        duration=info["duration"],
        thumbnail_url=info["thumbnail"],
        start_time=req.start_time,
        end_time=req.end_time,
        split_duration=req.split_duration,
        prompt=req.prompt,
        context_hint=req.context_hint,
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


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get job status and results."""
    job = await db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.get("/", response_model=list[JobResponse])
async def list_jobs(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List recent jobs."""
    result = await db.execute(
        select(TranscriptionJob).order_by(TranscriptionJob.created_at.desc()).limit(limit)
    )
    jobs = result.scalars().all()
    return [_job_to_response(j) for j in jobs]


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
                yield f"event: completed\ndata: {{\"job_id\": \"{job_id}\", \"message\": \"Already completed\"}}\n\n"
            else:
                yield f"event: error\ndata: {{\"job_id\": \"{job_id}\", \"error\": \"{job.error_message}\"}}\n\n"
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


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a job."""
    job = await db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()
    return {"message": "Job deleted"}


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
        segments=job.segments,
        mindmap_mermaid=job.mindmap_mermaid,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
    )
