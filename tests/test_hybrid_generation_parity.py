from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from feedops.api import hybrid_generation


@dataclass
class _HybridTable:
    db: "_HybridSupabase"
    name: str
    filters: dict[str, object]
    select_columns: tuple[str, ...]
    payload: dict | None
    single_mode: bool

    def __init__(self, db: "_HybridSupabase", name: str):
        self.db = db
        self.name = name
        self.filters = {}
        self.select_columns = ()
        self.payload = None
        self.single_mode = False

    def select(self, *columns, **_kwargs):
        self.select_columns = columns
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def maybe_single(self):
        self.single_mode = True
        return self

    def single(self):
        self.single_mode = True
        return self

    def insert(self, payload, **_kwargs):
        self.payload = payload
        self.db.record_write(self.name, "insert", payload)
        return self

    def update(self, payload, **_kwargs):
        self.payload = payload
        self.db.record_write(self.name, "update", payload)
        return self

    def upsert(self, payload, **_kwargs):
        self.payload = payload
        self.db.record_write(self.name, "upsert", payload)
        return self

    def execute(self):
        if self.name == "generated_content" and self.select_columns:
            key = (
                self.filters.get("master_sku"),
                self.filters.get("platform"),
                self.filters.get("content_type"),
            )
            row = self.db.generated_content.get(key)
            if row is None:
                return SimpleNamespace(data=None)
            if self.select_columns == ("id",):
                return SimpleNamespace(data={"id": row["id"]})
            if self.select_columns == ("candidate_content, approved_content",):
                return SimpleNamespace(
                    data={
                        "candidate_content": row.get("candidate_content"),
                        "approved_content": row.get("approved_content"),
                    }
                )
            return SimpleNamespace(data=dict(row))
        return SimpleNamespace(data=None)


class _HybridSupabase:
    def __init__(self):
        self.operations: list[dict] = []
        self.generated_content: dict[tuple[str, str, str], dict] = {}
        self._id_counter = 0

    def table(self, name: str) -> _HybridTable:
        return _HybridTable(self, name)

    def record_write(self, table: str, op: str, payload: dict):
        self.operations.append({"table": table, "op": op, "payload": payload})
        if table != "generated_content":
            return
        key = (
            payload.get("master_sku"),
            payload.get("platform"),
            payload.get("content_type"),
        )
        if not all(key):
            return
        existing = self.generated_content.get(key, {})
        if "id" not in existing:
            self._id_counter += 1
            existing["id"] = f"gc-{self._id_counter}"
        existing.update(payload)
        self.generated_content[key] = existing


def _seed_base_content(
    supabase: _HybridSupabase,
    *,
    base_sku: str,
    platform: str,
    content_type: str,
    content: str,
):
    supabase.record_write(
        "generated_content",
        "insert",
        {
            "master_sku": base_sku,
            "platform": platform,
            "content_type": content_type,
            "candidate_content": content,
            "approved_content": None,
        },
    )


def _fake_openai_client(response_content: str):
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_content))]
    )
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: completion)
        )
    )


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.delenv("FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.2")


@pytest.mark.asyncio
async def test_adapt_variant_content_google_description_uses_fallback_when_finish_regen_disabled(
    monkeypatch,
):
    monkeypatch.setenv("FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN", "1")
    supabase = _HybridSupabase()
    _seed_base_content(
        supabase,
        base_sku="SB-16",
        platform="google",
        content_type="description",
        content="Keep towels organized with this wall-mounted towel bar.",
    )

    monkeypatch.setattr(
        hybrid_generation.openai,
        "OpenAI",
        lambda api_key: _fake_openai_client(
            "Polished Nickel keeps towels organized. Choose from 28 designer finishes."
        ),
    )
    monkeypatch.setattr(hybrid_generation, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(hybrid_generation, "get_system_prompt_hash", lambda: "hash123")

    result = await hybrid_generation.adapt_variant_content(
        supabase=supabase,
        base_sku="SB-16",
        variant_sku="SB-18",
        platform="google",
        content_type="description",
        base_spec="16 inch",
        variant_spec="18 inch",
    )

    assert result["success"] is True
    assert "{FINISH_SENTENCE}" in result["content"]
    assert result["content"].count("{FINISH_SENTENCE}") == 1
    assert "Polished Nickel" not in result["content"]
    finish_rows = [
        op
        for op in supabase.operations
        if op["table"] == "variant_finish_sentences" and op["op"] == "upsert"
    ]
    assert len(finish_rows) == 1
    assert len(finish_rows[0]["payload"]["finish_sentences"]) == len(
        hybrid_generation.get_finish_list()
    )


@pytest.mark.asyncio
async def test_adapt_variant_content_google_description_falls_back_when_json_finish_sentences_incomplete(
    monkeypatch,
):
    supabase = _HybridSupabase()
    _seed_base_content(
        supabase,
        base_sku="SB-16",
        platform="google",
        content_type="description",
        content="Keep towels organized with this wall-mounted towel bar.",
    )
    incomplete_payload = {
        "content": "Antique Brass updates the look for this 18 inch profile.",
        "finish_sentences": {"Antique Brass": "Antique Brass adds warmth to this profile."},
    }
    monkeypatch.setattr(
        hybrid_generation.openai,
        "OpenAI",
        lambda api_key: _fake_openai_client(json.dumps(incomplete_payload)),
    )
    monkeypatch.setattr(hybrid_generation, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(hybrid_generation, "get_system_prompt_hash", lambda: "hash123")

    result = await hybrid_generation.adapt_variant_content(
        supabase=supabase,
        base_sku="SB-16",
        variant_sku="SB-18",
        platform="google",
        content_type="description",
        base_spec="16 inch",
        variant_spec="18 inch",
    )

    assert result["success"] is True
    assert "{FINISH_SENTENCE}" in result["content"]
    assert result["content"].count("{FINISH_SENTENCE}") == 1
    assert "Antique Brass" not in result["content"]
    finish_rows = [
        op
        for op in supabase.operations
        if op["table"] == "variant_finish_sentences" and op["op"] == "upsert"
    ]
    assert len(finish_rows) == 1
    assert len(finish_rows[0]["payload"]["finish_sentences"]) == len(
        hybrid_generation.get_finish_list()
    )


def test_variant_completion_tokens_policy_prevents_low_description_caps() -> None:
    assert hybrid_generation._variant_completion_tokens(
        platform="google", content_type="description", requires_json=True
    ) == 16000
    assert hybrid_generation._variant_completion_tokens(
        platform="bing", content_type="description", requires_json=True
    ) == 16000
    assert hybrid_generation._variant_completion_tokens(
        platform="shopify", content_type="description", requires_json=False
    ) == 8000
    assert hybrid_generation._variant_completion_tokens(
        platform="google", content_type="title", requires_json=False
    ) == 200
    assert hybrid_generation._variant_completion_tokens(
        platform="google", content_type="unknown_type", requires_json=True
    ) == 16000
