from __future__ import annotations

from types import SimpleNamespace

import pytest

import feedops.api.main as api_main
from feedops.models import ParentSKU, Variant


class _NoopProvider:
    name = "test/provider"


class _WriteTable:
    def __init__(self, db: "_WriteSupabase", table_name: str):
        self._db = db
        self._table_name = table_name

    def upsert(self, payload, **_kwargs):
        self._db.ops.append({"table": self._table_name, "op": "upsert", "payload": payload})
        return self

    def insert(self, payload, **_kwargs):
        self._db.ops.append({"table": self._table_name, "op": "insert", "payload": payload})
        return self

    def execute(self):
        return SimpleNamespace(data=[{"id": "row-1"}])


class _WriteSupabase:
    def __init__(self):
        self.ops: list[dict] = []

    def table(self, table_name: str):
        return _WriteTable(self, table_name)


def _sample_parent(master_sku: str) -> ParentSKU:
    return ParentSKU(
        master_sku=master_sku,
        category="Towel Bars",
        current_title="Sample",
        current_description="Sample description",
        variants=[
            Variant(
                option_sku=f"{master_sku}-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_us_1_1",
                position=1,
            )
        ],
    )


@pytest.mark.asyncio
async def test_optimize_single_sku_persists_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"
    writes = _WriteSupabase()
    persisted_master_skus: list[str] = []

    async def _fake_generate_with_metrics(**_kwargs):
        return {"content": "Base candidate content."}

    async def _fake_enforce_finish_sentence_parity(**_kwargs):
        return ("Base candidate content with {FINISH_SENTENCE}.", {"Antique Brass": "Sentence."})

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: writes)
    monkeypatch.setattr(api_main, "get_provider", lambda: _NoopProvider())
    monkeypatch.setattr(api_main, "get_system_prompt_hash", lambda: "hash123")
    monkeypatch.setattr(api_main, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(api_main, "build_evidence_table", lambda _parent: [])
    monkeypatch.setattr(api_main, "format_evidence_markdown", lambda _e: "evidence")
    monkeypatch.setattr(api_main, "_generate_with_metrics", _fake_generate_with_metrics)
    monkeypatch.setattr(api_main, "_enforce_finish_sentence_parity", _fake_enforce_finish_sentence_parity)
    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", lambda sku: _sample_parent(sku))
    monkeypatch.setattr(
        api_main,
        "_persist_generated_content_and_history",
        lambda **kwargs: persisted_master_skus.append(kwargs["master_sku"]),
    )

    request = api_main.OptimizeRequest(master_sku=requested, dry_run=False)
    response = await api_main.optimize_single_sku(request)

    assert response.success is True
    assert response.master_sku == canonical
    assert persisted_master_skus
    assert set(persisted_master_skus) == {canonical}
    finish_rows = [op for op in writes.ops if op["table"] == "variant_finish_sentences"]
    assert finish_rows
    assert {row["payload"]["master_sku"] for row in finish_rows} == {canonical}


@pytest.mark.asyncio
async def test_regenerate_content_writes_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"
    writes = _WriteSupabase()

    async def _fake_generate_with_metrics(**_kwargs):
        return {"content": "Generated description text."}

    async def _fake_enforce_finish_sentence_parity(**_kwargs):
        return ("Generated description with {FINISH_SENTENCE}.", {"Antique Brass": "Sentence."})

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: writes)
    monkeypatch.setattr(api_main, "get_provider", lambda: _NoopProvider())
    monkeypatch.setattr(api_main, "get_system_prompt_hash", lambda: "hash123")
    monkeypatch.setattr(api_main, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(api_main, "build_evidence_table", lambda _parent: [])
    monkeypatch.setattr(api_main, "format_evidence_markdown", lambda _e: "evidence")
    monkeypatch.setattr(api_main, "_generate_with_metrics", _fake_generate_with_metrics)
    monkeypatch.setattr(api_main, "_enforce_finish_sentence_parity", _fake_enforce_finish_sentence_parity)
    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", lambda sku: _sample_parent(sku))
    monkeypatch.setattr(
        api_main,
        "_lookup_generated_content_id",
        lambda **_kwargs: "row-1",
    )

    request = api_main.RegenerateRequest(
        master_sku=requested,
        platform="google",
        content_type="description",
    )
    response = await api_main.regenerate_content(request)

    assert response.success is True
    assert response.master_sku == canonical
    writes_for_generated_content = [
        op for op in writes.ops if op["table"] == "generated_content"
    ]
    assert writes_for_generated_content
    assert {
        op["payload"]["master_sku"] for op in writes_for_generated_content
    } == {canonical}
