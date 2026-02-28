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


def diagnostic_mode_enabled() -> bool:
    """Enable low-cost diagnostic behavior gates (safe default: disabled)."""
    return _truthy(os.getenv("FEEDOPS_DIAGNOSTIC_MODE"))


def diagnostic_force_low_cost_model_enabled() -> bool:
    """Force low-cost model selection while in diagnostic mode."""
    return _truthy(os.getenv("FEEDOPS_DIAGNOSTIC_FORCE_LOW_COST_MODEL", "1"))


def diagnostic_skip_finish_subcall_enabled() -> bool:
    """Skip finish sub-generation path during diagnostics when explicitly enabled."""
    return _truthy(os.getenv("FEEDOPS_DIAGNOSTIC_SKIP_FINISH_SUBCALL"))


def diagnostic_model_name() -> str:
    """Return configured diagnostic model override."""
    return (os.getenv("FEEDOPS_DIAGNOSTIC_MODEL") or "gpt-4.1-mini").strip()


def request_cost_usd_cap() -> float | None:
    """Optional per-request estimated cost cap; <=0 or invalid disables cap."""
    raw = os.getenv("FEEDOPS_PROVIDER_REQUEST_COST_USD_CAP")
    if not raw:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def ensure_generation_enabled(*, operation: str) -> None:
    """Raise 503 if generation is currently disabled by config."""
    if generation_disabled():
        raise HTTPException(
            status_code=503,
            detail=f"Generation is disabled by FEEDOPS_DISABLE_GENERATION ({operation})",
        )
