# tests/test_db.py
import pytest
from pathlib import Path
from feedops.db.schema import init_db, get_connection, log_optimization


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
        llm_provider="openai/gpt-4o",
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
