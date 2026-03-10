"""Orchestrates the full transcription pipeline."""
import logging
import traceback
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from models.job import TranscriptionJob, JobStatus, ASRProvider
from services.video_service import download_video, extract_audio, preprocess_audio, split_audio
from services.mindmap_service import generate_mindmap_from_segments, generate_mindmap_from_text
from services.sse_manager import sse_manager
from services import asr_openai, asr_docker, asr_huggingface
from services.llm_postprocess import postprocess_transcription, postprocess_segments

logger = logging.getLogger(__name__)


async def _update_job(db: AsyncSession, job: TranscriptionJob, **kwargs):
    """Update job fields and commit."""
    for key, value in kwargs.items():
        setattr(job, key, value)
    db.add(job)
    await db.commit()
    await db.refresh(job)


async def _publish_progress(job_id: str, progress: float, message: str, status: str = "progress"):
    """Publish progress via SSE."""
    await sse_manager.publish(job_id, status, {
        "job_id": job_id,
        "progress": round(progress, 1),
        "message": message,
    })


async def run_transcription_pipeline(db: AsyncSession, job: TranscriptionJob):
    """Run the full transcription pipeline for a job."""
    job_id = job.id

    try:
        # ── Step 1: Download Video ──
        await _update_job(db, job, status=JobStatus.DOWNLOADING, progress=0.0,
                          progress_message="Starting download...")
        await _publish_progress(job_id, 0, "Starting video download...", "downloading")

        async def on_download_progress(pct, msg):
            scaled = pct * 0.3  # Download is 0-30% of total
            await _update_job(db, job, progress=scaled, progress_message=msg)
            await _publish_progress(job_id, scaled, msg, "downloading")

        video_path = await download_video(job.url, job_id, on_progress=on_download_progress)
        await _update_job(db, job, video_path=str(video_path), progress=30.0,
                          progress_message="Download complete.")
        await _publish_progress(job_id, 30, "Download complete.", "downloading")

        # ── Step 2: Extract Audio ──
        await _update_job(db, job, status=JobStatus.EXTRACTING_AUDIO,
                          progress_message="Extracting audio...")
        await _publish_progress(job_id, 30, "Extracting audio...", "extracting_audio")

        async def on_extract_progress(pct, msg):
            scaled = 30 + pct * 0.1  # Extract is 30-40%
            await _update_job(db, job, progress=scaled, progress_message=msg)
            await _publish_progress(job_id, scaled, msg, "extracting_audio")

        audio_path = await extract_audio(
            video_path, job_id,
            start_time=job.start_time,
            end_time=job.end_time,
            on_progress=on_extract_progress,
        )

        # ── Step 2b: Preprocess Audio (noise reduction + normalization) ──
        await _publish_progress(job_id, 35, "Preprocessing audio...", "extracting_audio")
        audio_path = await preprocess_audio(audio_path, job_id, on_progress=on_extract_progress)

        await _update_job(db, job, audio_path=str(audio_path), progress=40.0,
                          progress_message="Audio extracted and preprocessed.")
        await _publish_progress(job_id, 40, "Audio ready.", "extracting_audio")

        # ── Step 3: Transcribe ──
        await _update_job(db, job, status=JobStatus.TRANSCRIBING,
                          progress_message="Starting transcription...")
        await _publish_progress(job_id, 40, "Starting transcription...", "transcribing")

        async def on_transcribe_progress(pct, msg):
            scaled = 40 + pct * 0.45  # Transcribe is 40-85%
            await _update_job(db, job, progress=scaled, progress_message=msg)
            await _publish_progress(job_id, scaled, msg, "transcribing")

        # Choose ASR provider
        if job.asr_provider == ASRProvider.OPENAI:
            asr_module = asr_openai
        elif job.asr_provider == ASRProvider.DOCKER:
            asr_module = asr_docker
        else:
            asr_module = asr_huggingface

        # Build kwargs — only OpenAI supports prompt; others ignore it
        transcribe_kwargs = {"language": job.language, "on_progress": on_transcribe_progress}
        if job.asr_provider == ASRProvider.OPENAI and job.prompt:
            transcribe_kwargs["prompt"] = job.prompt

        # Handle chunked transcription for long videos
        if job.split_duration and job.split_duration > 0:
            chunks = await split_audio(audio_path, job_id, job.split_duration)
            await _publish_progress(job_id, 42, f"Split into {len(chunks)} chunks.", "transcribing")
            result = await asr_module.transcribe_audio_chunked(
                chunks, **transcribe_kwargs
            )
        else:
            result = await asr_module.transcribe_audio(
                audio_path, **transcribe_kwargs
            )

        transcription_text = result.get("text", "")
        segments = result.get("segments", [])

        await _update_job(db, job, progress=78.0,
                          progress_message="Raw transcription done, cleaning up...")
        await _publish_progress(job_id, 78, "Raw transcription done, cleaning up with LLM...", "transcribing")

        # ── Step 3b: LLM Post-Correction ──
        async def on_postprocess_progress(pct, msg):
            scaled = 78 + pct * 0.07  # Post-processing is 78-85%
            await _update_job(db, job, progress=scaled, progress_message=msg)
            await _publish_progress(job_id, scaled, msg, "transcribing")

        context = job.context_hint or job.prompt or ""
        transcription_text = await postprocess_transcription(
            transcription_text, language=job.language, context_hint=context,
            on_progress=on_postprocess_progress,
        )
        if segments:
            segments = await postprocess_segments(
                segments, language=job.language, context_hint=context,
                on_progress=on_postprocess_progress,
            )

        await _update_job(db, job,
                          transcription=transcription_text,
                          segments=segments,
                          progress=85.0,
                          progress_message="Transcription complete.")
        await _publish_progress(job_id, 85, "Transcription complete.", "transcribing")

        # ── Step 4: Generate Mind-Map ──
        await _update_job(db, job, status=JobStatus.GENERATING_MINDMAP,
                          progress_message="Generating mind-map...")
        await _publish_progress(job_id, 85, "Generating mind-map...", "generating_mindmap")

        title = job.title or "Transcription"
        if segments:
            mindmap = generate_mindmap_from_segments(segments, title)
        else:
            mindmap = generate_mindmap_from_text(transcription_text, title)

        await _update_job(db, job,
                          mindmap_mermaid=mindmap,
                          status=JobStatus.COMPLETED,
                          progress=100.0,
                          progress_message="All done!")

        await _publish_progress(job_id, 100, "Transcription complete!", "completed")
        await sse_manager.publish(job_id, "completed", {
            "job_id": job_id,
            "transcription": transcription_text,
            "segments": segments,
            "mindmap": mindmap,
        })

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {traceback.format_exc()}")
        await _update_job(db, job,
                          status=JobStatus.FAILED,
                          error_message=str(e),
                          progress_message=f"Error: {str(e)}")
        await sse_manager.publish(job_id, "error", {
            "job_id": job_id,
            "error": str(e),
        })
