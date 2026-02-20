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
