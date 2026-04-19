"""Orchestrates the full transcription pipeline."""
import asyncio
import traceback
from pathlib import Path

from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from models.job import TranscriptionJob, JobStatus, ASRProvider, Platform
from services.video_service import download_video, extract_audio, preprocess_audio, split_audio, probe_duration
from services.subtitle_extractor import extract_subtitles
from services.sse_manager import sse_manager
from services import asr_openai, asr_docker
from services.llm_postprocess import postprocess_transcription, postprocess_segments


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


async def _download_video_background(url, job_id, expected_duration, db, job):
    """Download video in the background; update job on completion."""
    try:
        video_path = await download_video(url, job_id, expected_duration=expected_duration)
        await _update_job(db, job, video_path=str(video_path))
        logger.info(f"Background video download complete for job {job_id}")
        return video_path
    except Exception as e:
        logger.warning(f"Background video download failed for {job_id}: {e}")
        return None


async def run_transcription_pipeline(db: AsyncSession, job: TranscriptionJob):
    """Run the full transcription pipeline for a job."""
    job_id = job.id

    try:
        # ── Step 0: Try YouTube subtitle extraction (fast path) ──
        subtitle_result = None
        if job.platform == Platform.YOUTUBE and not job.start_time and not job.end_time:
            await _update_job(db, job, status=JobStatus.DOWNLOADING, progress=0.0,
                              progress_message="Checking for existing subtitles...")
            await _publish_progress(job_id, 0, "Checking for YouTube subtitles...", "downloading")

            async def on_sub_progress(pct, msg):
                scaled = pct * 0.15
                await _update_job(db, job, progress=scaled, progress_message=msg)
                await _publish_progress(job_id, scaled, msg, "downloading")

            try:
                subtitle_result = await extract_subtitles(
                    job.url, job_id, language=job.language, on_progress=on_sub_progress,
                )
            except Exception as e:
                logger.warning(f"Subtitle extraction failed for {job_id}, falling back to ASR: {e}")
                subtitle_result = None

            if subtitle_result:
                source = subtitle_result.get("source", "subtitles")
                source_label = "manual subtitles" if source == "manual" else "auto-captions"
                logger.info(f"Job {job_id}: using YouTube {source_label} (skipping ASR)")
                await _publish_progress(
                    job_id, 15,
                    f"Found YouTube {source_label}! Skipping audio transcription.",
                    "downloading",
                )

        # ── Step 1: Download Video ──
        # On subtitle path: download concurrently (non-blocking)
        # On ASR path: download and wait (we need the audio)
        download_task = None
        video_path = None

        if subtitle_result:
            # Fire-and-forget download for video player / MP3
            download_task = asyncio.create_task(
                _download_video_background(job.url, job_id, job.duration, db, job)
            )
            await _publish_progress(job_id, 30, "Downloading video in background...", "downloading")
        else:
            await _update_job(db, job, status=JobStatus.DOWNLOADING, progress=0.0,
                              progress_message="Starting download...")
            await _publish_progress(job_id, 0, "Starting video download...", "downloading")

            async def on_download_progress(pct, msg):
                scaled = pct * 0.3
                await _update_job(db, job, progress=scaled, progress_message=msg)
                await _publish_progress(job_id, scaled, msg, "downloading")

            video_path = await download_video(
                job.url, job_id,
                expected_duration=job.duration,
                on_progress=on_download_progress,
            )
            await _update_job(db, job, video_path=str(video_path), progress=30.0,
                              progress_message="Download complete.")
            await _publish_progress(job_id, 30, "Download complete.", "downloading")

        # ── Step 2: Extract Audio (skip if using subtitles) ──
        audio_path = None
        if not subtitle_result:
            await _update_job(db, job, status=JobStatus.EXTRACTING_AUDIO,
                              progress_message="Extracting audio...")
            await _publish_progress(job_id, 30, "Extracting audio...", "extracting_audio")

            async def on_extract_progress(pct, msg):
                scaled = 30 + pct * 0.1
                await _update_job(db, job, progress=scaled, progress_message=msg)
                await _publish_progress(job_id, scaled, msg, "extracting_audio")

            raw_audio_path = await extract_audio(
                video_path, job_id,
                start_time=job.start_time,
                end_time=job.end_time,
                on_progress=on_extract_progress,
            )

            raw_dur = await probe_duration(raw_audio_path)
            logger.debug(f"Job {job_id} — extracted audio duration: {raw_dur}s")

            await _publish_progress(job_id, 35, "Preprocessing audio...", "extracting_audio")
            audio_path = await preprocess_audio(raw_audio_path, job_id, on_progress=on_extract_progress)

            proc_dur = await probe_duration(audio_path)
            logger.debug(f"Job {job_id} — preprocessed audio duration: {proc_dur}s")

            await _update_job(db, job, progress=40.0,
                              progress_message="Audio extracted and preprocessed.")
            await _publish_progress(job_id, 40, "Audio ready.", "extracting_audio")
        else:
            await _publish_progress(job_id, 40, "Skipping audio extraction (using subtitles).", "extracting_audio")

        # ── Step 3: Transcribe (or use subtitles) ──
        await _update_job(db, job, status=JobStatus.TRANSCRIBING,
                          progress_message="Starting transcription...")
        await _publish_progress(job_id, 40, "Starting transcription...", "transcribing")

        if subtitle_result:
            transcription_text = subtitle_result.get("text", "")
            segments = subtitle_result.get("segments", [])
            source_label = "manual subtitles" if subtitle_result.get("source") == "manual" else "auto-captions"
            await _publish_progress(
                job_id, 75,
                f"Using YouTube {source_label} ({len(segments)} segments).",
                "transcribing",
            )
        else:
            async def on_transcribe_progress(pct, msg):
                scaled = 40 + pct * 0.45
                await _update_job(db, job, progress=scaled, progress_message=msg)
                await _publish_progress(job_id, scaled, msg, "transcribing")

            asr_module = asr_openai if job.asr_provider == ASRProvider.OPENAI else asr_docker

            transcribe_kwargs = {"language": job.language, "on_progress": on_transcribe_progress}
            if job.asr_provider == ASRProvider.OPENAI and job.prompt:
                transcribe_kwargs["prompt"] = job.prompt

            if job.split_duration and job.split_duration > 0:
                chunks = await split_audio(audio_path, job_id, job.split_duration)
                await _publish_progress(job_id, 42, f"Split into {len(chunks)} chunks.", "transcribing")
                result = await asr_module.transcribe_audio_chunked(chunks, **transcribe_kwargs)
            else:
                result = await asr_module.transcribe_audio(audio_path, **transcribe_kwargs)

            transcription_text = result.get("text", "")
            segments = result.get("segments", [])

        logger.debug(f"Job {job_id} — RAW ASR text (first 500 chars): {transcription_text[:500]!r}")

        # ── Step 3b: LLM Post-Correction (optional) ──
        if job.llm_cleanup:
            await _update_job(db, job, progress=78.0,
                              progress_message="Cleaning up with LLM...")
            await _publish_progress(job_id, 78, "Cleaning up transcription with LLM...", "transcribing")

            async def on_postprocess_progress(pct, msg):
                scaled = 78 + pct * 0.07
                await _update_job(db, job, progress=scaled, progress_message=msg)
                await _publish_progress(job_id, scaled, msg, "transcribing")

            context = job.prompt or ""
            raw_text_before_llm = transcription_text
            transcription_text = await postprocess_transcription(
                transcription_text, language=job.language, context_hint=context,
                on_progress=on_postprocess_progress,
            )

            if raw_text_before_llm[:100] != transcription_text[:100]:
                logger.debug(
                    f"Job {job_id} — LLM changed the beginning:\n"
                    f"  BEFORE: {raw_text_before_llm[:200]!r}\n"
                    f"  AFTER:  {transcription_text[:200]!r}"
                )
            if segments:
                segments = await postprocess_segments(
                    segments, language=job.language, context_hint=context,
                    on_progress=on_postprocess_progress,
                )

        await _update_job(db, job,
                          transcription=transcription_text,
                          segments=segments,
                          progress=95.0,
                          progress_message="Transcription complete.")
        await _publish_progress(job_id, 95, "Transcription complete.", "transcribing")

        # ── Step 4: Await background download if still running ──
        if download_task:
            await _publish_progress(job_id, 98, "Waiting for video download...", "progress")
            video_path = await download_task

        await _update_job(db, job,
                          status=JobStatus.COMPLETED,
                          progress=100.0,
                          progress_message="All done!")

        await _publish_progress(job_id, 100, "Transcription complete!", "completed")
        await sse_manager.publish(job_id, "completed", {
            "job_id": job_id,
            "transcription": transcription_text,
            "segments": segments,
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
