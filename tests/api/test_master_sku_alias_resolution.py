from __future__ import annotations

from types import SimpleNamespace

from feedops.api.sku_alias import build_master_sku_aliases, resolve_canonical_master_sku


class _AliasQuery:
    def __init__(self, table_name: str, rows_by_table: dict[str, list[dict]]):
        self._table_name = table_name
        self._rows_by_table = rows_by_table
        self._aliases: set[str] = set()

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, _column: str, values: list[str]):
        self._aliases = set(values)
        return self

    def limit(self, _value: int):
        return self

    def execute(self):
        source_rows = self._rows_by_table.get(self._table_name, [])
        rows = [row for row in source_rows if row.get("master_sku") in self._aliases]
        return SimpleNamespace(data=rows)


class _AliasSupabase:
    def __init__(self, rows_by_table: dict[str, list[dict]]):
        self._rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _AliasQuery(table_name, self._rows_by_table)


def test_build_master_sku_aliases_includes_hyphen_slash_variants() -> None:
    aliases = build_master_sku_aliases("WP-2TB-16-GAL")
    assert aliases[0] == "WP-2TB-16-GAL"
    assert "WP-2TB/16-GAL" in aliases


def test_resolve_canonical_master_sku_prefers_catalog_alias_match() -> None:
    supabase = _AliasSupabase(
        rows_by_table={
            "product_catalog": [{"master_sku": "WP-2TB/16-GAL"}],
            "variant_index": [],
        }
    )

    canonical = resolve_canonical_master_sku(supabase, "WP-2TB-16-GAL")
    assert canonical == "WP-2TB/16-GAL"


def test_resolve_canonical_master_sku_keeps_requested_when_present() -> None:
    supabase = _AliasSupabase(
        rows_by_table={
            "product_catalog": [
                {"master_sku": "WP-2TB-16-GAL"},
                {"master_sku": "WP-2TB/16-GAL"},
            ],
            "variant_index": [],
        }
    )

    canonical = resolve_canonical_master_sku(supabase, "WP-2TB-16-GAL")
    assert canonical == "WP-2TB-16-GAL"
