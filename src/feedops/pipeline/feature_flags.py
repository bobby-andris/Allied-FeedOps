"""Runtime feature flags for phased feed-generation rollout."""

from __future__ import annotations

import os


def _is_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_prompt_contract_v2_enabled() -> bool:
    return _is_enabled("PROMPT_CONTRACT_V2", True)


def is_intent_curator_v1_enabled() -> bool:
    return _is_enabled("INTENT_CURATOR_V1", True)


def is_segment_strategy_v1_enabled() -> bool:
    return _is_enabled("SEGMENT_STRATEGY_V1", True)


def is_query_intent_brief_v1_enabled() -> bool:
    return _is_enabled("QUERY_INTENT_BRIEF_V1", False)


def capture_flag_snapshot() -> dict:
    """Capture current state of all feature flags at call time.

    This function must be called at generation time — NOT at module import time.
    Calling at import time would capture the startup environment rather than the
    runtime environment, producing incorrect flag state for warm containers.

    Returns:
        dict: Mapping of flag name to boolean value for all known feature flags.
    """
    return {
        "PROMPT_CONTRACT_V2": is_prompt_contract_v2_enabled(),
        "INTENT_CURATOR_V1": is_intent_curator_v1_enabled(),
        "SEGMENT_STRATEGY_V1": is_segment_strategy_v1_enabled(),
        "QUERY_INTENT_BRIEF_V1": is_query_intent_brief_v1_enabled(),
    }
