# tests/test_db.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from feedops.db.schema import (
    cache_shopify_product,
    get_cached_merchant_center_items,
    get_cached_shopify_product,
    get_connection,
    init_db,
    log_keyword_intent_snapshot,
    log_optimization,
    upsert_merchant_center_items,
)


def test_init_db_creates_tables(tmp_path):
    """init_db creates optimization_runs table."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='optimization_runs'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    """Calling init_db twice doesn't error."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # Should not raise


def test_log_optimization_records_run(tmp_path):
    """log_optimization saves run to database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    run_id = log_optimization(
        db_path=db_path,
        master_sku="1031/18",
        llm_provider="openai/gpt-5.2",
        quality_score=85.0,
        factual_accuracy=9,
        approval_status="approved",
        status="success",
    )

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM optimization_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()

    assert row["master_sku"] == "1031/18"
    assert row["quality_score"] == 85.0
    assert row["status"] == "success"


def test_log_optimization_records_data_source(tmp_path):
    """log_optimization stores data source when provided."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    run_id = log_optimization(
        db_path=db_path,
        master_sku="1031/18",
        llm_provider="openai/gpt-5.2",
        quality_score=85.0,
        factual_accuracy=9,
        approval_status="approved",
        status="success",
        data_source="shopify_cached",
    )

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT data_source FROM optimization_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()

    assert row["data_source"] == "shopify_cached"


def test_log_keyword_intent_snapshot_records_keywords(tmp_path):
    """Keyword intent snapshots can be persisted per run."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    run_id = log_optimization(
        db_path=db_path,
        master_sku="1031/18",
        llm_provider="openai/gpt-5.2",
        quality_score=85.0,
        factual_accuracy=9,
        approval_status="approved",
        status="success",
    )
    snap_id = log_keyword_intent_snapshot(
        db_path=db_path,
        master_sku="1031/18",
        item_group_id="4542872518788",
        item_ids=["shopify_US_4542872518788_32118222192772"],
        external_keywords=["wall mount towel bar"],
        keyword_intent_master=["wall mount towel bar", "bath towel holder"],
        optimization_run_id=run_id,
    )

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM keyword_intent_snapshots WHERE id = ?", (snap_id,)
    ).fetchone()
    conn.close()

    assert row["master_sku"] == "1031/18"
    assert row["item_group_id"] == "4542872518788"
    assert json.loads(row["item_ids_json"]) == [
        "shopify_US_4542872518788_32118222192772"
    ]
    assert json.loads(row["external_keywords_json"]) == ["wall mount towel bar"]
    assert json.loads(row["keyword_intent_master_json"]) == [
        "wall mount towel bar",
        "bath towel holder",
    ]


def test_cache_shopify_product_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    init_db(db_path)
    payload = {"id": "gid://shopify/Product/123", "title": "Test Product"}
    cache_shopify_product(
        master_sku="TEST-1", product_id="123", payload=payload, ttl_hours=4.0
    )

    cached = get_cached_shopify_product("TEST-1", max_age_hours=6.0)
    assert cached == payload


def test_get_cached_shopify_product_expired(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    init_db(db_path)
    payload = {"id": "gid://shopify/Product/123", "title": "Test Product"}
    cache_shopify_product(
        master_sku="TEST-2", product_id="123", payload=payload, ttl_hours=1.0
    )

    stale_time = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE shopify_products SET fetched_at = ? WHERE master_sku = ?",
        (stale_time, "TEST-2"),
    )
    conn.commit()
    conn.close()

    cached = get_cached_shopify_product("TEST-2", max_age_hours=2.0)
    assert cached is None


def test_get_cached_merchant_center_items_filters_by_master_sku(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    init_db(db_path)
    fetched_at = datetime.now(timezone.utc).isoformat()
    product_payload = {
        "id": "gid://shopify/Product/999",
        "legacyResourceId": "999",
        "variants": {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/111",
                    "legacyResourceId": "111",
                    "sku": "ABC-123-ABR",
                    "selectedOptions": [{"name": "Finish", "value": "Antique Brass"}],
                },
                {
                    "id": "gid://shopify/ProductVariant/222",
                    "legacyResourceId": "222",
                    "sku": "ABC-123-ORB",
                    "selectedOptions": [
                        {"name": "Finish", "value": "Oil Rubbed Bronze"}
                    ],
                },
            ]
        },
    }
    cache_shopify_product(
        master_sku="ABC-123",
        product_id="999",
        payload=product_payload,
        ttl_hours=24.0,
    )

    gmc_match = {"offerId": "shopify_US_999_111", "fetched_at": fetched_at}
    gmc_other = {"offerId": "shopify_US_555_777", "fetched_at": fetched_at}
    upsert_merchant_center_items(db_path, [gmc_match, gmc_other])

    cached = get_cached_merchant_center_items("ABC-123", max_age_hours=6.0)
    assert [item["offerId"] for item in cached] == ["shopify_US_999_111"]
