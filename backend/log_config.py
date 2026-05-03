"""
Centralized log-level configuration for all modules.

Adjust levels here to control verbosity per module.
Valid levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL
"""

# Default level applied to any module not listed below
DEFAULT_LEVEL = "INFO"

# Per-module overrides
MODULE_LEVELS = {
    "backend.services.transcription_orchestrator": "INFO",
    "backend.services.video_service": "INFO",
    "backend.services.asr_openai": "INFO",
    "backend.services.asr_docker": "INFO",
    "backend.services.llm_postprocess": "INFO",
    "backend.services.subtitle_extractor": "INFO",
    "backend.services.sse_manager": "WARNING",
    "backend.routers.jobs": "INFO",
    "backend.db.database": "INFO",
    "uvicorn": "INFO",
    "uvicorn.access": "WARNING",
    "sqlalchemy": "WARNING",
}


def log_filter(record: dict) -> bool:
    """Loguru filter that applies per-module log levels."""
    name = record["name"] or ""
    # Find the most specific matching module
    level = DEFAULT_LEVEL
    best_match_len = 0
    for module, module_level in MODULE_LEVELS.items():
        if (name == module or name.startswith(module + ".")) and len(module) > best_match_len:
            level = module_level
            best_match_len = len(module)
    return record["level"].no >= _level_no(level)


def _level_no(level_name: str) -> int:
    """Convert level name to its numeric value."""
    from loguru import logger

    return logger.level(level_name).no
