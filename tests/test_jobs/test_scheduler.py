from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from feedops.jobs.scheduler import get_all_active_skus, get_stale_skus


class _FakeQuery:
    def __init__(self, rows: list[dict], default_limit: int = 1000):
        self._rows = rows
        self._default_limit = default_limit
        self._selected: list[str] | None = None
        self._order_by: str | None = None
        self._desc = False
        self._range: tuple[int, int] | None = None

    def select(self, columns: str):
        self._selected = [column.strip() for column in columns.split(",") if column.strip()]
        return self

    def order(self, column: str, desc: bool = False):
        self._order_by = column
        self._desc = desc
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def execute(self):
        rows = list(self._rows)

        if self._order_by:
            rows.sort(key=lambda row: row.get(self._order_by) or "", reverse=self._desc)

        if self._range is None:
            rows = rows[: self._default_limit]
        else:
            start, end = self._range
            rows = rows[start : end + 1]

        if self._selected is not None:
            rows = [{column: row.get(column) for column in self._selected} for row in rows]

        return SimpleNamespace(data=rows)


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]], default_limit: int = 1000):
        self._tables = tables
        self._default_limit = default_limit

    def table(self, table_name: str):
        return _FakeQuery(self._tables.get(table_name, []), default_limit=self._default_limit)


@patch("feedops.db.supabase_client.get_client")
def test_get_all_active_skus_reads_all_variant_index_pages(mock_get_client):
    rows = [{"master_sku": f"SKU-{index:04d}"} for index in range(1, 1506)]
    mock_get_client.return_value = _FakeClient({"variant_index": rows}, default_limit=1000)

    skus = get_all_active_skus()

    assert len(skus) == 1505
    assert skus[0] == "SKU-0001"
    assert skus[-1] == "SKU-1505"


@patch("feedops.db.supabase_client.get_client")
def test_get_stale_skus_uses_fetched_at_with_collected_at_fallback(mock_get_client):
    mock_get_client.return_value = _FakeClient(
        {
            "variant_index": [
                {"master_sku": "A"},
                {"master_sku": "B"},
                {"master_sku": "C"},
            ],
            "search_queries": [
                {
                    "master_sku": "A",
                    "fetched_at": "2999-01-01T00:00:00+00:00",
                    "collected_at": "2000-01-01T00:00:00+00:00",
                },
                {
                    "master_sku": "B",
                    "fetched_at": None,
                    "collected_at": "2999-01-01T00:00:00+00:00",
                },
            ],
            "performance_baselines": [
                {"master_sku": "A", "created_at": "2999-01-01T00:00:00+00:00"},
                {"master_sku": "B", "created_at": "2999-01-01T00:00:00+00:00"},
                {"master_sku": "C", "created_at": "2999-01-01T00:00:00+00:00"},
            ],
        },
        default_limit=1000,
    )

    stale = get_stale_skus(days_threshold=7)

    assert stale == ["C"]


@patch("feedops.db.supabase_client.get_client")
def test_get_stale_skus_includes_missing_sku_beyond_first_variant_index_page(mock_get_client):
    variant_rows = [{"master_sku": f"SKU-{index:04d}"} for index in range(1, 1202)]
    fresh_skus = [row["master_sku"] for row in variant_rows[:-1]]

    mock_get_client.return_value = _FakeClient(
        {
            "variant_index": variant_rows,
            "search_queries": [
                {
                    "master_sku": sku,
                    "fetched_at": "2999-01-01T00:00:00+00:00",
                    "collected_at": "2999-01-01T00:00:00+00:00",
                }
                for sku in fresh_skus
            ],
            "performance_baselines": [
                {"master_sku": sku, "created_at": "2999-01-01T00:00:00+00:00"}
                for sku in fresh_skus
            ],
        },
        default_limit=1000,
    )

    stale = get_stale_skus(days_threshold=7)

    assert stale == ["SKU-1201"]
