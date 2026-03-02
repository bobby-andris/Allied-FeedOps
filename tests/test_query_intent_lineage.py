from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from feedops.api import main as api_main


class _CaptureTable:
    def __init__(self, db: "_CaptureSupabase", name: str):
        self._db = db
        self._name = name
        self._filters: dict[str, object] = {}
        self._select_columns: tuple[str, ...] = ()

    def insert(self, payload, **_kwargs):
        if self._name == "generated_content":
            self._db.store_generated_content(payload)
        self._db.operations.append({"op": "insert", "table": self._name, "payload": payload})
        return self

    def update(self, payload, **_kwargs):
        if self._name == "generated_content":
            self._db.store_generated_content(payload)
        self._db.operations.append({"op": "update", "table": self._name, "payload": payload})
        return self

    def select(self, *columns, **_kwargs):
        self._select_columns = columns
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def execute(self):
        if self._name == "generated_content" and self._select_columns:
            row = self._db.find_generated_content(self._filters)
            return SimpleNamespace(data=row)
        return SimpleNamespace(data=None)


@dataclass
class _CaptureSupabase:
    operations: list[dict]

    def __init__(self):
        self.operations = []
        self._generated_content: dict[tuple[str, str, str], dict] = {}
        self._id_counter = 0

    def table(self, name: str) -> _CaptureTable:
        return _CaptureTable(self, name)

    def store_generated_content(self, payload: dict):
        key = (
            payload.get("master_sku"),
            payload.get("platform"),
            payload.get("content_type"),
        )
        existing = self._generated_content.get(key, {})
        if "id" not in existing:
            self._id_counter += 1
            existing["id"] = f"generated-{self._id_counter}"
        existing.update(payload)
        self._generated_content[key] = existing

    def find_generated_content(self, filters: dict[str, object]) -> dict | None:
        key = (
            filters.get("master_sku"),
            filters.get("platform"),
            filters.get("content_type"),
        )
        row = self._generated_content.get(key)
        return dict(row) if row else None


def test_extract_query_intent_generation_diagnostics_only_returns_dict() -> None:
    assert api_main._extract_query_intent_generation_diagnostics(None) == {}
    assert api_main._extract_query_intent_generation_diagnostics({"query_intent_diagnostics": "nope"}) == {}
    assert api_main._extract_query_intent_generation_diagnostics(
        {"query_intent_diagnostics": {"query_intent_brief_enabled": True}}
    ) == {"query_intent_brief_enabled": True}


def test_persist_regeneration_result_embeds_query_intent_flag_and_diagnostics(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QUERY_INTENT_BRIEF_V1", "1")
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-query-intent-lineage")
    monkeypatch.setattr(
        api_main,
        "get_platform_system_prompt_hash",
        lambda platform: f"platform-hash-{platform}",
    )

    db = _CaptureSupabase()
    query_prompt = "<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>"
    diagnostics = {
        "query_intent_brief_enabled": True,
        "query_intent_data_sufficiency": True,
        "query_intent_primary_count": 2,
        "query_intent_source_query_count": 4,
        "query_intent_disabled_reason": None,
    }

    api_main._persist_regeneration_result(
        supabase=db,
        master_sku="1031/18",
        platform="google",
        content_type="title",
        content="Skyline 18 Inch Towel Bar",
        generation_model="fake/provider",
        prompt_hash="prompt-hash-1",
        system_prompt="system-google",
        user_prompt=query_prompt,
        feedback_text=None,
        mode="regenerate",
        tokens_used=150,
        cost_usd=0.12,
        generation_diagnostics=diagnostics,
        latency_ms=120,
        provider_attempt_count=1,
        parse_retry_count=0,
        request_id="req-query-intent-lineage",
        idempotency_key="idem-1",
    )

    history_writes = [
        op for op in db.operations if op["table"] == "regeneration_history" and op["op"] == "insert"
    ]
    assert len(history_writes) == 1

    payload = history_writes[0]["payload"]
    assert "<query_intent_brief>" in payload["user_prompt"]
    assert payload["feature_flags_active"]["QUERY_INTENT_BRIEF_V1"] is True
    assert payload["feature_flags_active"]["generation_diagnostics"] == diagnostics


def test_lineage_hash_changes_when_query_intent_prompt_changes(monkeypatch) -> None:
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-query-intent-hashes")
    monkeypatch.setattr(
        api_main,
        "get_platform_system_prompt_hash",
        lambda platform: f"platform-hash-{platform}",
    )

    db = _CaptureSupabase()

    api_main._persist_regeneration_result(
        supabase=db,
        master_sku="1031/18",
        platform="google",
        content_type="title",
        content="Skyline 18 Inch Towel Bar",
        generation_model="fake/provider",
        prompt_hash="prompt-hash-a",
        system_prompt="system-google",
        user_prompt="<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>",
        feedback_text=None,
        mode="regenerate",
        request_id="req-query-intent-hashes",
        idempotency_key="idem-a",
    )
    api_main._persist_regeneration_result(
        supabase=db,
        master_sku="1031/18",
        platform="google",
        content_type="title",
        content="Skyline 18 Inch Wall Mount Towel Bar",
        generation_model="fake/provider",
        prompt_hash="prompt-hash-b",
        system_prompt="system-google",
        user_prompt="<query_intent_brief>\n- solid brass towel bar\n</query_intent_brief>",
        feedback_text=None,
        mode="regenerate",
        request_id="req-query-intent-hashes",
        idempotency_key="idem-b",
    )

    history_rows = [
        op["payload"]
        for op in db.operations
        if op["table"] == "regeneration_history" and op["op"] == "insert"
    ]
    assert len(history_rows) == 2
    assert history_rows[0]["assembled_prompt_hash"] != history_rows[1]["assembled_prompt_hash"]
