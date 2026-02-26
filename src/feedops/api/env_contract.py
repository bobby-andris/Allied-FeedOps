"""Runtime environment contract for Cloud Run parity.

This module defines a small fail-fast contract for required runtime
configuration so production misconfiguration fails at startup instead of mid-run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class RuntimeEnvContractError(RuntimeError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class EnvContractResult:
    """Validation result for runtime contract checks."""

    ok: bool
    missing: tuple[str, ...]


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def validate_runtime_env_contract(env: dict[str, str] | None = None) -> EnvContractResult:
    """Validate required runtime env vars.

    Contract is enabled by default. Set ``FEEDOPS_ENV_CONTRACT_STRICT=0`` to disable.
    """

    runtime_env = os.environ if env is None else env
    strict = _truthy(runtime_env.get("FEEDOPS_ENV_CONTRACT_STRICT", "1"))
    if not strict:
        return EnvContractResult(ok=True, missing=())

    missing: list[str] = []

    has_supabase_url = bool(
        (runtime_env.get("SUPABASE_URL") or runtime_env.get("NEXT_PUBLIC_SUPABASE_URL") or "").strip()
    )
    has_supabase_key = bool(
        (
            runtime_env.get("SUPABASE_KEY")
            or runtime_env.get("SUPABASE_SERVICE_ROLE_KEY")
            or runtime_env.get("SUPABASE_SERVICE_KEY")
            or runtime_env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
            or ""
        ).strip()
    )
    has_llm_provider_key = bool(
        (
            runtime_env.get("OPENAI_API_KEY")
            or runtime_env.get("GEMINI_API_KEY")
            or ""
        ).strip()
    )

    if not has_supabase_url:
        missing.append("SUPABASE_URL|NEXT_PUBLIC_SUPABASE_URL")
    if not has_supabase_key:
        missing.append(
            "SUPABASE_KEY|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_SERVICE_KEY|NEXT_PUBLIC_SUPABASE_ANON_KEY"
        )
    if not has_llm_provider_key:
        missing.append("OPENAI_API_KEY|GEMINI_API_KEY")

    if missing:
        raise RuntimeEnvContractError(
            "Runtime env contract failed: missing required configuration: "
            + ", ".join(missing)
        )

    return EnvContractResult(ok=True, missing=())
