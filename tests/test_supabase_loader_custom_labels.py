from __future__ import annotations

from types import SimpleNamespace


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _Client:
    def __init__(self, product_rows, label_rows):
        self._product_rows = product_rows
        self._label_rows = label_rows

    def table(self, name: str):
        if name == "product_catalog":
            return _Query(self._product_rows)
        if name == "variant_index":
            return _Query(self._label_rows)
        raise AssertionError(f"Unexpected table requested: {name}")


def test_load_parent_sku_from_supabase_attaches_custom_labels(monkeypatch):
    from feedops.api import supabase_loader

    product_rows = [
        {
            "master_sku": "SKU-1",
            "option_sku": "SKU-1-PC",
            "finish_name": "Polished Chrome",
            "finish_code": "PC",
            "gmc_id": "shopify_US_1_1",
            "position": 1,
            "category": "Toilet Paper Holders",
            "title": "Sample Product",
            "narrative_copy": "Sample narrative",
            "collection": "Dottingham",
            "core_sku": "SKU-1",
        }
    ]
    label_rows = [
        {
            "gmc_offer_id": "shopify_us_1_1",
            "custom_labels": {
                "custom_label_0": "toilet paper holders",
                "customLabel1": "high",
            },
        }
    ]

    monkeypatch.setattr(
        supabase_loader,
        "get_client",
        lambda: _Client(product_rows, label_rows),
    )
    monkeypatch.setattr(
        supabase_loader,
        "resolve_canonical_master_sku",
        lambda _client, sku: sku,
    )

    parent = supabase_loader.load_parent_sku_from_supabase("SKU-1")

    assert parent is not None
    assert parent.master_sku == "SKU-1"
    assert parent.merchant_center_items == [
        {
            "offerId": "shopify_us_1_1",
            "customLabel0": "toilet paper holders",
            "customLabel1": "high",
            "customLabel2": None,
            "customLabel3": None,
            "customLabel4": None,
        }
    ]

