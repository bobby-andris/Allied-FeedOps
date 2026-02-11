"""Runtime kill switches and reliability toggles for generation paths."""

from __future__ import annotations

import os

from fastapi import HTTPException


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def generation_disabled() -> bool:
    """Global generation kill switch (safe default: disabled = False)."""
    return _truthy(os.getenv("FEEDOPS_DISABLE_GENERATION"))


def finish_sentence_regeneration_disabled() -> bool:
    """Finish sentence path kill switch (safe default: disabled = False)."""
    return _truthy(os.getenv("FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN"))


def finish_sentence_regeneration_enabled() -> bool:
    return not finish_sentence_regeneration_disabled()


def ensure_generation_enabled(*, operation: str) -> None:
    """Raise 503 if generation is currently disabled by config."""
    if generation_disabled():
        raise HTTPException(
            status_code=503,
            detail=f"Generation is disabled by FEEDOPS_DISABLE_GENERATION ({operation})",
        )

