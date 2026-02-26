from __future__ import annotations

import pytest

from feedops.api.env_contract import RuntimeEnvContractError, validate_runtime_env_contract


def test_runtime_env_contract_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_ENV_CONTRACT_STRICT", "0")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = validate_runtime_env_contract()
    assert result.ok is True
    assert result.missing == ()


def test_runtime_env_contract_raises_on_missing_required_values(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_ENV_CONTRACT_STRICT", "1")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeEnvContractError) as exc:
        validate_runtime_env_contract()

    msg = str(exc.value)
    assert "SUPABASE_URL|NEXT_PUBLIC_SUPABASE_URL" in msg
    assert "OPENAI_API_KEY|GEMINI_API_KEY" in msg


def test_runtime_env_contract_accepts_primary_keys(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_ENV_CONTRACT_STRICT", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "service-role")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = validate_runtime_env_contract()
    assert result.ok is True


def test_runtime_env_contract_accepts_fallback_aliases(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_ENV_CONTRACT_STRICT", "1")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")

    result = validate_runtime_env_contract()
    assert result.ok is True
