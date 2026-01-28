from datetime import datetime, timedelta, timezone

import pytest

from feedops.loaders import unified_loader as ul
from feedops.models.parent_sku import ParentSKU


def _make_parent(master_sku: str) -> ParentSKU:
    return ParentSKU(
        master_sku=master_sku,
        category="Test",
        current_title="Title",
        current_description="Description",
        variants=[],
    )


def test_load_parent_sku_unified_sets_data_source_cached(monkeypatch):
    cached_payload = {"id": "gid://shopify/Product/1", "variants": {"nodes": []}}

    monkeypatch.setattr(
        ul, "get_cached_shopify_product", lambda *_args, **_kwargs: cached_payload
    )
    monkeypatch.setattr(
        ul,
        "_build_parent_from_shopify_payload",
        lambda *_args, **_kwargs: _make_parent("ABC"),
    )
    monkeypatch.setattr(ul, "_load_gmc_items", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        ul,
        "_get_cached_shopify_fetched_at",
        lambda *_args, **_kwargs: datetime.now(timezone.utc),
    )

    parent = ul.load_parent_sku_unified("ABC", force_refresh=False, cache_ttl_hours=24)

    assert parent is not None
    assert parent.data_source == "shopify_cached"


def test_load_parent_sku_unified_sets_data_source_fresh(monkeypatch):
    monkeypatch.setattr(
        ul, "get_cached_shopify_product", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        ul,
        "fetch_shopify_product",
        lambda *_args, **_kwargs: {
            "id": "gid://shopify/Product/2",
            "variants": {"nodes": []},
        },
    )
    monkeypatch.setattr(ul, "cache_shopify_product", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ul,
        "_build_parent_from_shopify_payload",
        lambda *_args, **_kwargs: _make_parent("DEF"),
    )
    monkeypatch.setattr(ul, "_load_gmc_items", lambda *_args, **_kwargs: [])

    parent = ul.load_parent_sku_unified("DEF", force_refresh=False, cache_ttl_hours=24)

    assert parent is not None
    assert parent.data_source == "shopify_fresh"


def test_load_parent_sku_unified_sets_data_source_csv_fallback(monkeypatch):
    monkeypatch.setattr(
        ul, "get_cached_shopify_product", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(ul, "fetch_shopify_product", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ul, "resolve_catalog_path", lambda *_args, **_kwargs: "fake.csv"
    )
    monkeypatch.setattr(ul, "load_catalog", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        ul, "get_parent_sku", lambda *_args, **_kwargs: _make_parent("GHI")
    )

    parent = ul.load_parent_sku_unified("GHI", force_refresh=False, cache_ttl_hours=24)

    assert parent is not None
    assert parent.data_source == "csv_fallback"


def test_get_cached_shopify_age_hours_returns_age(monkeypatch):
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        ul, "_get_cached_shopify_fetched_at", lambda *_args, **_kwargs: base_time
    )

    now = base_time + timedelta(hours=2, minutes=30)
    monkeypatch.setattr(ul, "datetime", datetime)
    monkeypatch.setattr(ul, "timezone", timezone)
    monkeypatch.setattr(ul, "datetime", datetime)
    monkeypatch.setattr(ul, "_now_utc", lambda: now)

    age = ul.get_cached_shopify_age_hours("ABC")

    assert age == pytest.approx(2.5, rel=1e-3)
