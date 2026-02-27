from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import feedops.api.main as api_main
from feedops.models import ParentSKU, Variant


class _NoopProvider:
    name = "test/provider"


class _TableQuery:
    def __init__(self, db: "_FakeSupabase", table_name: str):
        self._db = db
        self._table_name = table_name
        self._op = "select"
        self._payload: dict | None = None
        self._filters: dict[str, object] = {}

    def select(self, _columns: str):
        # Preserve write intent for insert/update(...).select("id") chains.
        if self._op == "select":
            self._op = "select"
        return self

    def limit(self, _n: int):
        return self

    def eq(self, key: str, value):
        self._filters[key] = value
        return self

    def in_(self, _key: str, _values: list):
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def upsert(self, payload: dict, **_kwargs):
        self._op = "upsert"
        self._payload = deepcopy(payload)
        return self

    def update(self, payload: dict, **_kwargs):
        self._op = "update"
        self._payload = deepcopy(payload)
        return self

    def insert(self, payload: dict | list[dict], **_kwargs):
        self._op = "insert"
        self._payload = deepcopy(payload if isinstance(payload, dict) else payload[0])
        return self

    def execute(self):
        if self._op == "select":
            if self._table_name == "generated_content":
                row = self._db.generated_content_row
                if not row:
                    return SimpleNamespace(data=None)
                for key, value in self._filters.items():
                    if row.get(key) != value:
                        return SimpleNamespace(data=None)
                return SimpleNamespace(data=deepcopy(row))
            if self._table_name == "sku_corrections":
                return SimpleNamespace(data=[])
            return SimpleNamespace(data=None)

        payload = deepcopy(self._payload or {})
        self._db.ops.append({"table": self._table_name, "op": self._op, "payload": payload})

        if self._table_name == "generated_content":
            if self._op == "insert":
                generated_id = payload.get("id") or "generated-new"
                payload["id"] = generated_id
                self._db.generated_content_row = payload
                return SimpleNamespace(data={"id": generated_id})
            if self._op == "update":
                row = self._db.generated_content_row or {}
                if self._filters.get("id") and row.get("id") != self._filters["id"]:
                    return SimpleNamespace(data=None)
                row.update(payload)
                row.setdefault("id", "generated-existing")
                self._db.generated_content_row = row
                return SimpleNamespace(data={"id": row["id"]})
            if self._op == "upsert":
                row = self._db.generated_content_row or {}
                row.update(payload)
                row.setdefault("id", "generated-upsert")
                self._db.generated_content_row = row
                return SimpleNamespace(data=[{"id": row["id"]}])

        if self._table_name == "regeneration_history" and self._op == "insert":
            self._db.history_rows.append(payload)
            return SimpleNamespace(data=[{"id": "history-1"}])

        return SimpleNamespace(data=[{"id": "row-1"}])


class _FakeSupabase:
    def __init__(self, generated_content_row: dict | None = None):
        self.generated_content_row = deepcopy(generated_content_row)
        self.ops: list[dict] = []
        self.history_rows: list[dict] = []

    def table(self, table_name: str):
        return _TableQuery(self, table_name)


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


def _base_generated_payload(content: str) -> dict:
    return {
        "google_title": content,
        "prompt_hashes": {"google": "hash-google"},
        "system_prompts": {"google": "sys-google"},
        "user_prompts": {"google": "user-google"},
        "latency_by_platform": {"google": 125},
    }


@pytest.mark.asyncio
async def test_regenerate_content_writes_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"
    writes = _FakeSupabase()

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: writes)
    monkeypatch.setattr(api_main, "get_provider", lambda: _NoopProvider())
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-regen-canonical")
    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", lambda sku: _sample_parent(sku))
    async def _fake_generate_per_platform(**_kwargs):
        return _base_generated_payload("Canonical regenerated title")
    monkeypatch.setattr(
        api_main,
        "generate_per_platform",
        _fake_generate_per_platform,
    )

    request = api_main.RegenerateRequest(
        master_sku=requested,
        platform="google",
        content_type="title",
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


@pytest.mark.asyncio
async def test_regenerate_content_no_change_returns_idempotent_without_writes(monkeypatch):
    canonical = "WP-2TB/16-GAL"
    existing_row = {
        "id": "generated-existing",
        "master_sku": canonical,
        "platform": "google",
        "content_type": "title",
        "candidate_content": "No change title",
        "version": 4,
    }
    db = _FakeSupabase(generated_content_row=existing_row)

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: db)
    monkeypatch.setattr(api_main, "get_provider", lambda: _NoopProvider())
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-no-change")
    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", lambda sku: _sample_parent(sku))
    async def _fake_generate_per_platform(**_kwargs):
        return _base_generated_payload("No change title")
    monkeypatch.setattr(
        api_main,
        "generate_per_platform",
        _fake_generate_per_platform,
    )

    request = api_main.RegenerateRequest(
        master_sku=canonical,
        platform="google",
        content_type="title",
    )
    response = await api_main.regenerate_content(request)

    assert response.state == "no_change"
    assert response.idempotent is True
    assert response.version == 4
    assert response.generated_content_id == "generated-existing"
    assert response.request_id == "req-no-change"
    assert not [op for op in db.ops if op["table"] == "generated_content"]
    assert not [op for op in db.ops if op["table"] == "regeneration_history"]


@pytest.mark.asyncio
async def test_regenerate_content_change_updates_version_and_writes_single_history_row(monkeypatch):
    canonical = "WP-2TB/16-GAL"
    existing_row = {
        "id": "generated-existing",
        "master_sku": canonical,
        "platform": "google",
        "content_type": "title",
        "candidate_content": "Old title",
        "version": 2,
    }
    db = _FakeSupabase(generated_content_row=existing_row)

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: db)
    monkeypatch.setattr(api_main, "get_provider", lambda: _NoopProvider())
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-changed")
    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", lambda sku: _sample_parent(sku))
    async def _fake_generate_per_platform(**_kwargs):
        return _base_generated_payload("Updated title")
    monkeypatch.setattr(
        api_main,
        "generate_per_platform",
        _fake_generate_per_platform,
    )

    request = api_main.RegenerateRequest(
        master_sku=canonical,
        platform="google",
        content_type="title",
    )
    response = await api_main.regenerate_content(request)

    assert response.state == "completed"
    assert response.idempotent is False
    assert response.version == 3
    assert response.generated_content_id == "generated-existing"
    assert response.request_id == "req-changed"

    generated_writes = [op for op in db.ops if op["table"] == "generated_content"]
    history_writes = [op for op in db.ops if op["table"] == "regeneration_history"]
    assert len(generated_writes) == 1
    assert generated_writes[0]["op"] == "update"
    assert len(history_writes) == 1
    assert history_writes[0]["payload"]["generated_content_id"] == "generated-existing"
    assert history_writes[0]["payload"]["request_id"] == "req-changed"


@pytest.mark.asyncio
async def test_regenerate_content_async_mode_queues_job_without_immediate_generation(monkeypatch):
    canonical = "WP-2TB/16-GAL"
    db = _FakeSupabase()
    thread_call: dict[str, object] = {}

    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(
        api_main,
        "resolve_canonical_master_sku",
        lambda _supabase, _master_sku: canonical,
        raising=False,
    )
    monkeypatch.setattr(api_main, "get_client", lambda: db)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-async")

    def _fake_run_async(async_func, request_id=None, **kwargs):
        thread_call["async_func"] = async_func
        thread_call["request_id"] = request_id
        thread_call["kwargs"] = kwargs
        return None

    monkeypatch.setattr(api_main, "run_async_in_thread", _fake_run_async)

    request = api_main.RegenerateRequest(
        master_sku=canonical,
        platform="google",
        content_type="title",
        async_mode=True,
    )
    response = await api_main.regenerate_content(request)

    assert isinstance(response, api_main.RegenerateJobResponse)
    assert response.success is True
    assert response.status == "pending"
    assert response.request_id == "req-async"
    assert response.master_sku == canonical
    assert response.job_id == "row-1"

    queued_job_writes = [
        op for op in db.ops if op["table"] == "generation_jobs" and op["op"] == "insert"
    ]
    assert len(queued_job_writes) == 1
    assert queued_job_writes[0]["payload"]["job_type"] == "regenerate"
    assert queued_job_writes[0]["payload"]["status"] == "pending"

    assert thread_call["request_id"] == "req-async"
    kwargs = thread_call["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["job_id"] == "row-1"
    assert kwargs["request_payload"]["async_mode"] is False

    assert not [op for op in db.ops if op["table"] == "generated_content"]
    assert not [op for op in db.ops if op["table"] == "regeneration_history"]


@pytest.mark.asyncio
async def test_process_regenerate_job_marks_failed_when_running_transition_raises(monkeypatch):
    class _FailRunningUpdateQuery(_TableQuery):
        def execute(self):
            if (
                self._table_name == "generation_jobs"
                and self._op == "update"
                and (self._payload or {}).get("status") == "running"
            ):
                raise RuntimeError("running transition failed")
            return super().execute()

    class _FailRunningUpdateSupabase(_FakeSupabase):
        def table(self, table_name: str):
            return _FailRunningUpdateQuery(self, table_name)

    db = _FailRunningUpdateSupabase()
    called = {"execute": False}

    async def _should_not_execute(**_kwargs):
        called["execute"] = True
        raise AssertionError("regeneration should not execute if running update fails")

    monkeypatch.setattr(api_main, "get_client", lambda: db)
    monkeypatch.setattr(api_main, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(api_main, "_execute_regeneration_request", _should_not_execute)

    await api_main.process_regenerate_job(
        job_id="job-1",
        request_payload={
            "master_sku": "WP-2TB/16-GAL",
            "platform": "google",
            "content_type": "title",
            "async_mode": False,
        },
    )

    assert called["execute"] is False
    failed_updates = [
        op
        for op in db.ops
        if op["table"] == "generation_jobs"
        and op["op"] == "update"
        and op["payload"].get("status") == "failed"
    ]
    assert len(failed_updates) == 1
    assert "running transition failed" in str(failed_updates[0]["payload"].get("error", ""))
