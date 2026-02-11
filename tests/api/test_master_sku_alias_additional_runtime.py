from __future__ import annotations

from dataclasses import dataclass

import pytest

from feedops.api import performance_baseline as performance_module
from feedops.api import search_insights as search_module


@dataclass
class _Result:
    data: list[dict]
    error: object = None


class _Query:
    def __init__(self, table_name: str, rows_by_table: dict[str, list[dict]]):
        self._table_name = table_name
        self._rows_by_table = rows_by_table
        self._eq_filters: dict[str, object] = {}
        self._limit: int | None = None
        self._gte_filters: dict[str, int] = {}

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def eq(self, column: str, value: object):
        self._eq_filters[column] = value
        return self

    def gte(self, column: str, value: int):
        self._gte_filters[column] = value
        return self

    def execute(self):
        rows = list(self._rows_by_table.get(self._table_name, []))
        for column, value in self._eq_filters.items():
            rows = [row for row in rows if row.get(column) == value]
        for column, value in self._gte_filters.items():
            rows = [row for row in rows if int(row.get(column, 0)) >= value]
        if self._limit is not None:
            rows = rows[: self._limit]
        return _Result(data=rows)


class _Supabase:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self._rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _Query(table_name, self._rows_by_table)


@pytest.mark.asyncio
async def test_capture_baseline_uses_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"

    rows_by_table = {
        "variant_index": [
            {"master_sku": canonical, "gmc_offer_id": "shopify_us_123_456"},
        ]
    }
    supabase = _Supabase(rows_by_table)
    captured_master_skus: list[str] = []

    def _fake_capture_google_baseline(**kwargs):
        captured_master_skus.append(kwargs["master_sku"])
        return {"impressions": 10}

    monkeypatch.setattr(performance_module, "get_client", lambda: supabase)
    monkeypatch.setattr(
        performance_module,
        "_capture_google_baseline",
        _fake_capture_google_baseline,
    )
    monkeypatch.setattr(
        performance_module,
        "resolve_canonical_master_sku",
        lambda _supabase, sku, **_kwargs: canonical if sku == requested else sku,
        raising=False,
    )

    request = performance_module.CaptureBaselineRequest(
        master_skus=[requested],
        platforms=["google"],
    )
    response = await performance_module.capture_baseline(request)

    assert response.success is True
    assert response.skus_processed == 1
    assert captured_master_skus == [canonical]


@pytest.mark.asyncio
async def test_search_terms_query_filters_with_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"

    supabase = _Supabase(
        rows_by_table={
            "search_queries": [
                {"master_sku": canonical, "impressions": 100, "query_text": "query"},
            ]
        }
    )

    monkeypatch.setattr(search_module, "get_client", lambda: supabase)
    monkeypatch.setattr(
        search_module,
        "resolve_canonical_master_sku",
        lambda _supabase, sku, **_kwargs: canonical if sku == requested else sku,
        raising=False,
    )

    response = await search_module.get_search_terms(
        master_sku=requested,
        min_impressions=1,
    )

    assert response.success is True
    assert response.count == 1
    assert response.data[0]["master_sku"] == canonical


@pytest.mark.asyncio
async def test_aggregated_terms_query_filters_with_canonical_master_sku(monkeypatch):
    requested = "WP-2TB-16-GAL"
    canonical = "WP-2TB/16-GAL"

    supabase = _Supabase(
        rows_by_table={
            "search_queries_by_master_sku": [
                {"master_sku": canonical, "total_impressions": 50},
            ]
        }
    )

    monkeypatch.setattr(search_module, "get_client", lambda: supabase)
    monkeypatch.setattr(
        search_module,
        "resolve_canonical_master_sku",
        lambda _supabase, sku, **_kwargs: canonical if sku == requested else sku,
        raising=False,
    )

    response = await search_module.get_aggregated_terms(master_sku=requested)

    assert response.success is True
    assert response.count == 1
    assert response.data[0]["master_sku"] == canonical
