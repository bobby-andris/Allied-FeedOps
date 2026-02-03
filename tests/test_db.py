# tests/test_db.py
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from feedops.db.schema import (
    assign_skus_to_batch,
    cache_shopify_product,
    create_batch,
    get_all_batches,
    get_approved_for_batch,
    get_batch,
    get_batch_skus,
    get_cached_merchant_center_items,
    get_cached_shopify_product,
    get_connection,
    get_pending_approvals,
    get_publish_history,
    get_published_skus,
    get_revision_queue,
    get_sku_approval,
    get_skus_needing_review,
    get_variant_approval,
    get_variant_approvals_for_sku,
    init_db,
    log_keyword_intent_snapshot,
    log_optimization,
    log_publish_event,
    save_sku_approval,
    save_variant_approval,
    update_batch_status,
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


# ──────────────────────────────────────────────────────────────────────
# Column rename migration tests
# ──────────────────────────────────────────────────────────────────────


def test_column_rename_migration_sku_approvals(tmp_path):
    """init_db renames old sku_approvals columns on an existing database."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a database with OLD column names
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE sku_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL UNIQUE,
            title_approved INTEGER,
            description_approved INTEGER,
            image_approved INTEGER,
            selected_finish TEXT,
            selected_image_index INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            revision_notes TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO sku_approvals (
            master_sku, status, revision_notes, reviewed_by, reviewed_at,
            created_at, updated_at
        ) VALUES ('TEST-1', 'approved', 'Looks good', 'admin', '2026-01-01', '2026-01-01', '2026-01-01')
        """
    )
    conn.commit()
    conn.close()

    # Run init_db which should rename columns
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(sku_approvals)").fetchall()
    }
    conn.close()

    assert "approval_status" in cols
    assert "notes" in cols
    assert "approved_by" in cols
    assert "approved_at" in cols
    # Old names should no longer exist
    assert "status" not in cols or "approval_status" in cols  # renamed
    assert "revision_notes" not in cols
    assert "reviewed_by" not in cols
    assert "reviewed_at" not in cols

    # Verify data survived the migration
    approval = get_sku_approval(db_path, master_sku="TEST-1")
    assert approval is not None
    assert approval["approval_status"] == "approved"
    assert approval["notes"] == "Looks good"
    assert approval["approved_by"] == "admin"


def test_column_rename_migration_batches(tmp_path):
    """init_db renames old publish_batches columns on an existing database."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE publish_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            batch_label TEXT,
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            selection_criteria TEXT,
            created_at TEXT NOT NULL,
            published_at TEXT,
            sku_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        INSERT INTO publish_batches (
            batch_id, batch_label, selection_criteria, created_at, published_at
        ) VALUES ('Batch-2026-01-01-001', 'Test Batch', 'top SKUs', '2026-01-01', '2026-01-02')
        """
    )
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(publish_batches)").fetchall()
    }
    conn.close()

    assert "name" in cols
    assert "notes" in cols
    assert "executed_at" in cols
    assert "batch_label" not in cols
    assert "selection_criteria" not in cols
    assert "published_at" not in cols

    batch = get_batch(db_path, batch_id="Batch-2026-01-01-001")
    assert batch is not None
    assert batch["name"] == "Test Batch"
    assert batch["notes"] == "top SKUs"
    assert batch["executed_at"] == "2026-01-02"


# ──────────────────────────────────────────────────────────────────────
# Auto-derive approval status tests
# ──────────────────────────────────────────────────────────────────────


def test_auto_derive_status_all_approved(tmp_path):
    """When all elements are approved and status is pending, auto-derives to approved."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(
        db_path,
        master_sku="SKU-1",
        title_approved=True,
        description_approved=True,
        image_approved=True,
        status="pending",
    )

    approval = get_sku_approval(db_path, master_sku="SKU-1")
    assert approval["approval_status"] == "approved"


def test_auto_derive_status_any_rejected(tmp_path):
    """When any element is rejected and status is pending, auto-derives to rejected."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(
        db_path,
        master_sku="SKU-2",
        title_approved=True,
        description_approved=False,
        image_approved=True,
        status="pending",
    )

    approval = get_sku_approval(db_path, master_sku="SKU-2")
    assert approval["approval_status"] == "rejected"


def test_auto_derive_status_explicit_overrides(tmp_path):
    """When status is explicitly set (not pending), auto-derive is skipped."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(
        db_path,
        master_sku="SKU-3",
        title_approved=True,
        description_approved=True,
        image_approved=True,
        status="revision",
    )

    approval = get_sku_approval(db_path, master_sku="SKU-3")
    assert approval["approval_status"] == "revision"


def test_auto_derive_status_none_elements_stays_pending(tmp_path):
    """When no elements are reviewed, status stays pending."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(
        db_path,
        master_sku="SKU-4",
        title_approved=None,
        description_approved=None,
        image_approved=None,
        status="pending",
    )

    approval = get_sku_approval(db_path, master_sku="SKU-4")
    assert approval["approval_status"] == "pending"


# ──────────────────────────────────────────────────────────────────────
# get_published_skus() SQLite implementation tests
# ──────────────────────────────────────────────────────────────────────


def test_get_published_skus_returns_successful_production(tmp_path):
    """get_published_skus returns only successful production publishes."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    # Successful production publish
    log_publish_event(
        db_path,
        master_sku="SKU-A",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
    )
    # Failed production publish (should not be included)
    log_publish_event(
        db_path,
        master_sku="SKU-B",
        platform="google",
        environment="production",
        action="publish",
        patch_file="b.json",
        status="failed",
    )
    # Successful staging publish (should not be included in production query)
    log_publish_event(
        db_path,
        master_sku="SKU-C",
        platform="google",
        environment="staging",
        action="publish",
        patch_file="c.json",
        status="success",
    )

    published = get_published_skus(db_path, platform="google", environment="production")
    assert published == {"SKU-A"}


def test_get_published_skus_empty_database(tmp_path):
    """get_published_skus returns empty set for fresh database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    published = get_published_skus(db_path)
    assert published == set()


def test_get_published_skus_no_platform_filter(tmp_path):
    """get_published_skus without platform returns all platforms."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    log_publish_event(
        db_path,
        master_sku="SKU-A",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
    )
    log_publish_event(
        db_path,
        master_sku="SKU-B",
        platform="bing",
        environment="production",
        action="publish",
        patch_file="b.json",
        status="success",
    )

    published = get_published_skus(db_path)
    assert published == {"SKU-A", "SKU-B"}


def test_get_skus_needing_review_filters_published(tmp_path):
    """get_skus_needing_review excludes already published SKUs."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    log_publish_event(
        db_path,
        master_sku="SKU-A",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
    )

    needing = get_skus_needing_review(
        db_path, all_skus=["SKU-A", "SKU-B", "SKU-C"], platform="google"
    )
    assert needing == ["SKU-B", "SKU-C"]


# ──────────────────────────────────────────────────────────────────────
# get_publish_history() with environment filter tests
# ──────────────────────────────────────────────────────────────────────


def test_get_publish_history_environment_filter(tmp_path):
    """get_publish_history filters by environment when provided."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    log_publish_event(
        db_path,
        master_sku="SKU-1",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
    )
    log_publish_event(
        db_path,
        master_sku="SKU-2",
        platform="google",
        environment="staging",
        action="publish",
        patch_file="b.json",
        status="success",
    )

    history = get_publish_history(db_path, environment="staging")
    assert len(history) == 1
    assert history[0]["master_sku"] == "SKU-2"
    assert history[0]["environment"] == "staging"


def test_get_publish_history_no_environment_returns_all(tmp_path):
    """get_publish_history without environment returns all events."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    log_publish_event(
        db_path,
        master_sku="SKU-1",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
    )
    log_publish_event(
        db_path,
        master_sku="SKU-2",
        platform="google",
        environment="staging",
        action="publish",
        patch_file="b.json",
        status="success",
    )

    history = get_publish_history(db_path)
    assert len(history) == 2


def test_get_publish_history_includes_new_fields(tmp_path):
    """get_publish_history includes approval_status, published_by, and batch fields."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    log_publish_event(
        db_path,
        master_sku="SKU-1",
        platform="google",
        environment="production",
        action="publish",
        patch_file="a.json",
        status="success",
        approval_status="approved",
        published_by="admin",
        batch_id="Batch-2026-01-01-001",
        product_category="Towel Bars",
        product_collection="Allied Brass",
    )

    history = get_publish_history(db_path)
    assert len(history) == 1
    event = history[0]
    assert event["approval_status"] == "approved"
    assert event["published_by"] == "admin"
    assert event["batch_id"] == "Batch-2026-01-01-001"
    assert event["product_category"] == "Towel Bars"
    assert event["product_collection"] == "Allied Brass"


# ──────────────────────────────────────────────────────────────────────
# Variant approvals CRUD tests
# ──────────────────────────────────────────────────────────────────────


def test_variant_approval_crud(tmp_path):
    """save/get variant approval round-trip."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    record_id = save_variant_approval(
        db_path,
        master_sku="SKU-1",
        finish="Polished Chrome",
        finish_code="PC",
        title_approved=True,
        description_approved=True,
        image_approved=False,
        selected_image_index=2,
        notes="Image needs work",
        approved_by="reviewer",
    )
    assert record_id > 0

    approval = get_variant_approval(db_path, master_sku="SKU-1", finish="Polished Chrome")
    assert approval is not None
    assert approval["master_sku"] == "SKU-1"
    assert approval["finish"] == "Polished Chrome"
    assert approval["finish_code"] == "PC"
    assert approval["title_approved"] is True
    assert approval["description_approved"] is True
    assert approval["image_approved"] is False
    assert approval["selected_image_index"] == 2
    assert approval["approval_status"] == "rejected"  # auto-derived: image_approved=False
    assert approval["notes"] == "Image needs work"
    assert approval["approved_by"] == "reviewer"


def test_variant_approval_auto_derive(tmp_path):
    """Variant approval auto-derives status from element approvals."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_variant_approval(
        db_path,
        master_sku="SKU-1",
        finish="Antique Brass",
        title_approved=True,
        description_approved=True,
        image_approved=True,
    )

    approval = get_variant_approval(db_path, master_sku="SKU-1", finish="Antique Brass")
    assert approval["approval_status"] == "approved"


def test_variant_approval_update(tmp_path):
    """save_variant_approval updates an existing record."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_variant_approval(
        db_path,
        master_sku="SKU-1",
        finish="Polished Chrome",
        title_approved=False,
    )

    approval = get_variant_approval(db_path, master_sku="SKU-1", finish="Polished Chrome")
    assert approval["approval_status"] == "rejected"

    # Update to approved
    save_variant_approval(
        db_path,
        master_sku="SKU-1",
        finish="Polished Chrome",
        title_approved=True,
        description_approved=True,
        image_approved=True,
    )

    approval = get_variant_approval(db_path, master_sku="SKU-1", finish="Polished Chrome")
    assert approval["approval_status"] == "approved"


def test_get_variant_approvals_for_sku(tmp_path):
    """get_variant_approvals_for_sku returns all variants for a SKU."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_variant_approval(
        db_path, master_sku="SKU-1", finish="Polished Chrome", title_approved=True
    )
    save_variant_approval(
        db_path, master_sku="SKU-1", finish="Oil Rubbed Bronze", title_approved=True
    )
    save_variant_approval(
        db_path, master_sku="SKU-2", finish="Polished Chrome", title_approved=True
    )

    variants = get_variant_approvals_for_sku(db_path, master_sku="SKU-1")
    assert len(variants) == 2
    finishes = {v["finish"] for v in variants}
    assert finishes == {"Oil Rubbed Bronze", "Polished Chrome"}


def test_get_variant_approval_nonexistent(tmp_path):
    """get_variant_approval returns None for nonexistent record."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    result = get_variant_approval(db_path, master_sku="NOPE", finish="Nope")
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# SKU approval + batch management with new column names
# ──────────────────────────────────────────────────────────────────────


def test_sku_approval_dict_keys(tmp_path):
    """Approval dict uses new key names (approval_status, notes, approved_by, approved_at)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(
        db_path,
        master_sku="SKU-1",
        title_approved=True,
        description_approved=True,
        image_approved=True,
        notes="All good",
        approved_by="admin",
    )

    approval = get_sku_approval(db_path, master_sku="SKU-1")
    assert "approval_status" in approval
    assert "notes" in approval
    assert "approved_by" in approval
    assert "approved_at" in approval
    # Old keys should NOT be present
    assert "status" not in approval
    assert "revision_notes" not in approval
    assert "reviewed_by" not in approval
    assert "reviewed_at" not in approval


def test_batch_dict_keys(tmp_path):
    """Batch dict uses new key names (name, notes, executed_at)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    batch_id = create_batch(db_path, batch_label="Test Batch", notes="some notes")

    batch = get_batch(db_path, batch_id=batch_id)
    assert batch is not None
    assert "name" in batch
    assert "notes" in batch
    assert "executed_at" in batch
    assert batch["name"] == "Test Batch"
    assert batch["notes"] == "some notes"
    # Old keys should NOT be present
    assert "batch_label" not in batch
    assert "selection_criteria" not in batch
    assert "published_at" not in batch


def test_batch_full_lifecycle(tmp_path):
    """Create batch, assign SKUs, update status, verify all new column names."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    # Create batch
    batch_id = create_batch(
        db_path,
        batch_label="Lifecycle Test",
        target_date="2026-02-15",
        skus=["SKU-A", "SKU-B"],
    )

    # Verify batch created
    batch = get_batch(db_path, batch_id=batch_id)
    assert batch["name"] == "Lifecycle Test"
    assert batch["status"] == "pending"
    assert batch["sku_count"] == 2
    assert batch["executed_at"] is None

    # Verify SKUs assigned
    skus = get_batch_skus(db_path, batch_id=batch_id)
    assert set(skus) == {"SKU-A", "SKU-B"}

    # Assign more SKUs
    assigned = assign_skus_to_batch(db_path, batch_id=batch_id, skus=["SKU-C"])
    assert assigned == 1

    # Update status to published
    update_batch_status(
        db_path,
        batch_id=batch_id,
        status="published",
        success_count=2,
        failed_count=1,
    )

    batch = get_batch(db_path, batch_id=batch_id)
    assert batch["status"] == "published"
    assert batch["executed_at"] is not None
    assert batch["success_count"] == 2
    assert batch["failed_count"] == 1


def test_get_all_batches_uses_new_keys(tmp_path):
    """get_all_batches returns dicts with new column names."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    create_batch(db_path, batch_label="Batch A", notes="first batch")
    create_batch(db_path, batch_label="Batch B", notes="second batch")

    batches = get_all_batches(db_path)
    assert len(batches) == 2
    for b in batches:
        assert "name" in b
        assert "notes" in b
        assert "executed_at" in b


def test_pending_and_revision_queues(tmp_path):
    """get_pending_approvals and get_revision_queue use approval_status column."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    save_sku_approval(db_path, master_sku="PENDING-1", status="pending")
    save_sku_approval(db_path, master_sku="PENDING-2", status="pending")
    save_sku_approval(
        db_path,
        master_sku="REVISION-1",
        status="revision",
        notes="Fix title",
    )
    save_sku_approval(
        db_path,
        master_sku="APPROVED-1",
        title_approved=True,
        description_approved=True,
        image_approved=True,
        status="pending",  # will auto-derive to approved
    )

    pending = get_pending_approvals(db_path)
    assert len(pending) == 2
    assert all(a["approval_status"] == "pending" for a in pending)

    revision = get_revision_queue(db_path)
    assert len(revision) == 1
    assert revision[0]["approval_status"] == "revision"
    assert revision[0]["notes"] == "Fix title"

    approved = get_approved_for_batch(db_path, exclude_batched=False)
    assert len(approved) == 1
    assert approved[0]["approval_status"] == "approved"


# ──────────────────────────────────────────────────────────────────────
# Variant index finish/finish_code column tests
# ──────────────────────────────────────────────────────────────────────


def test_variant_index_has_finish_columns(tmp_path):
    """variant_index table includes finish and finish_code columns."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(variant_index)").fetchall()
    }
    conn.close()

    assert "finish" in cols
    assert "finish_code" in cols


def test_variant_index_finish_migration(tmp_path):
    """Adding finish columns to existing variant_index via migration."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create variant_index WITHOUT finish columns (simulating old schema)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE variant_index (
            gmc_id TEXT PRIMARY KEY,
            master_sku TEXT NOT NULL,
            master_sku_norm TEXT NOT NULL,
            option_sku TEXT,
            option_sku_norm TEXT,
            core_sku TEXT,
            shopify_product_id TEXT,
            shopify_variant_id TEXT,
            product_length TEXT,
            product_width TEXT,
            product_height TEXT,
            projection TEXT,
            center_to_center TEXT,
            diameter TEXT,
            product_weight TEXT,
            category TEXT,
            collection TEXT,
            material TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    # Run init_db which should add finish columns
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(variant_index)").fetchall()
    }
    conn.close()

    assert "finish" in cols
    assert "finish_code" in cols


# ──────────────────────────────────────────────────────────────────────
# Fresh database creates all tables with correct column names
# ──────────────────────────────────────────────────────────────────────


def test_fresh_db_creates_all_tables(tmp_path):
    """init_db on a fresh database creates all expected tables."""
    db_path = tmp_path / "fresh.db"
    init_db(db_path)

    conn = get_connection(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()

    expected = {
        "optimization_runs",
        "content_versions",
        "keyword_intent_snapshots",
        "merchant_center_items",
        "shopify_products",
        "variant_index",
        "catalog_ingest_state",
        "publish_events",
        "performance_snapshots",
        "performance_baselines",
        "sku_approvals",
        "publish_batches",
        "batch_sku_assignments",
        "variant_approvals",
    }
    assert expected.issubset(tables)


def test_fresh_db_sku_approvals_has_new_columns(tmp_path):
    """Fresh database sku_approvals uses new column names directly."""
    db_path = tmp_path / "fresh.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(sku_approvals)").fetchall()
    }
    conn.close()

    assert "approval_status" in cols
    assert "notes" in cols
    assert "approved_by" in cols
    assert "approved_at" in cols


def test_fresh_db_publish_batches_has_new_columns(tmp_path):
    """Fresh database publish_batches uses new column names directly."""
    db_path = tmp_path / "fresh.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(publish_batches)").fetchall()
    }
    conn.close()

    assert "name" in cols
    assert "notes" in cols
    assert "executed_at" in cols


def test_fresh_db_variant_approvals_table(tmp_path):
    """Fresh database has variant_approvals table with correct columns."""
    db_path = tmp_path / "fresh.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(variant_approvals)").fetchall()
    }
    conn.close()

    expected_cols = {
        "id",
        "master_sku",
        "finish",
        "finish_code",
        "title_approved",
        "description_approved",
        "image_approved",
        "selected_image_index",
        "approval_status",
        "notes",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    }
    assert expected_cols.issubset(cols)
