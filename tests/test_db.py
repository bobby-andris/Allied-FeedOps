# tests/test_db.py
import json
import pytest
from pathlib import Path
from feedops.db.schema import (
    init_db,
    get_connection,
    log_optimization,
    log_keyword_intent_snapshot,
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
    assert json.loads(row["item_ids_json"]) == ["shopify_US_4542872518788_32118222192772"]
    assert json.loads(row["external_keywords_json"]) == ["wall mount towel bar"]
    assert json.loads(row["keyword_intent_master_json"]) == [
        "wall mount towel bar",
        "bath towel holder",
    ]
