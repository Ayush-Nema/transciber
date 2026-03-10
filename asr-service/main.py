"""
ASR Microservice using faster-whisper (CTranslate2).
Runs as a standalone Docker container.
Optimized for Hindi language transcription.
"""
import os
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Configuration
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")  # tiny, base, small, medium, large-v3
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8 for CPU efficiency

app = FastAPI(title="ASR Service", version="1.0.0")

# Load model at startup
logger.info(f"Loading faster-whisper model: {MODEL_SIZE} (device={DEVICE}, compute={COMPUTE_TYPE})")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
logger.info("Model loaded successfully.")


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_SIZE, "device": DEVICE}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default="hi"),
):
    """
    Transcribe an audio file.
    Returns text and timestamped segments.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Save uploaded audio to temp file
    suffix = Path(file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        logger.info(f"Transcribing: {file.filename} (language={language}, size={len(content)} bytes)")

        # Run transcription
        # Use None for language to enable auto-detection, or specific language code
        lang = language if language and language != "auto" else None

        segments_iter, info = model.transcribe(
            tmp_path,
            language=lang,
            beam_size=5,
            vad_filter=True,          # Voice Activity Detection
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
            word_timestamps=False,     # Segment-level timestamps only (faster)
            condition_on_previous_text=True,
        )

        # Collect segments
        segments = []
        full_text_parts = []

        for segment in segments_iter:
            seg_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
            }
            segments.append(seg_data)
            full_text_parts.append(segment.text.strip())

        full_text = " ".join(full_text_parts)

        logger.info(
            f"Transcription complete: {len(segments)} segments, "
            f"detected_language={info.language}, probability={info.language_probability:.2f}"
        )

        return {
            "text": full_text,
            "segments": segments,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
        }

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
