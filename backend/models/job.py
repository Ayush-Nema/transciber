import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Float, Integer, Enum, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    GENERATING_MINDMAP = "generating_mindmap"
    COMPLETED = "completed"
    FAILED = "failed"


class Platform(str, enum.Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class ASRProvider(str, enum.Enum):
    OPENAI = "openai"
    DOCKER = "docker"
    HUGGINGFACE = "huggingface"


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(String(2048))
    platform: Mapped[Platform] = mapped_column(Enum(Platform))
    asr_provider: Mapped[ASRProvider] = mapped_column(Enum(ASRProvider), default=ASRProvider.OPENAI)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[str] = mapped_column(String(500), default="")

    # Video metadata
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Transcription settings
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # seconds
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)    # seconds
    language: Mapped[str] = mapped_column(String(10), default="hi")         # Default Hindi
    split_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds, for chunking
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)         # Whisper prompt for context priming
    context_hint: Mapped[str | None] = mapped_column(Text, nullable=True)   # Hint for LLM post-correction

    # Results
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # timestamped segments
    mindmap_mermaid: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
