"""SQLite database schema and operations."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime


def get_connection(db_path: Path | str) -> sqlite3.Connection:
    """Get SQLite connection.

    Args:
        db_path: Path to database file.

    Returns:
        SQLite connection with row factory.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str) -> None:
    """Initialize database with required tables.

    Args:
        db_path: Path to database file.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimization_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            variant_sku TEXT,
            timestamp TEXT NOT NULL,
            llm_provider TEXT NOT NULL,
            llm_model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            quality_score REAL,
            factual_accuracy INTEGER,
            approval_status TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS content_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            version_type TEXT NOT NULL,
            title TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            optimization_run_id INTEGER,
            FOREIGN KEY (optimization_run_id) REFERENCES optimization_runs(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_intent_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            item_group_id TEXT,
            item_ids_json TEXT,
            external_keywords_json TEXT,
            keyword_intent_master_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            optimization_run_id INTEGER,
            FOREIGN KEY (optimization_run_id) REFERENCES optimization_runs(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_master_sku
        ON optimization_runs(master_sku)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_versions_master_sku
        ON content_versions(master_sku)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_keyword_intent_master_sku
        ON keyword_intent_snapshots(master_sku)
    """)

    conn.commit()
    conn.close()


def log_optimization(
    db_path: Path | str,
    master_sku: str,
    llm_provider: str,
    quality_score: float,
    factual_accuracy: int,
    approval_status: str,
    status: str,
    variant_sku: str | None = None,
    llm_model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error_message: str | None = None,
) -> int:
    """Log an optimization run to the database.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU that was optimized.
        llm_provider: Provider name (e.g., 'openai/gpt-5.2').
        quality_score: Composite quality score (0-100).
        factual_accuracy: Factual accuracy score (0-10).
        approval_status: 'approved', 'revise', or 'rejected'.
        status: 'success', 'failed', or 'rejected'.
        variant_sku: Optional specific variant.
        llm_model: Optional model name.
        prompt_tokens: Optional token count.
        completion_tokens: Optional token count.
        error_message: Optional error message if failed.

    Returns:
        ID of the inserted row.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO optimization_runs (
            master_sku, variant_sku, timestamp, llm_provider, llm_model,
            prompt_tokens, completion_tokens, quality_score, factual_accuracy,
            approval_status, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            variant_sku,
            datetime.now().isoformat(),
            llm_provider,
            llm_model,
            prompt_tokens,
            completion_tokens,
            quality_score,
            factual_accuracy,
            approval_status,
            status,
            error_message,
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def log_keyword_intent_snapshot(
    db_path: Path | str,
    *,
    master_sku: str,
    item_group_id: str | None = None,
    item_ids: list[str] | None = None,
    external_keywords: list[str] | None = None,
    keyword_intent_master: list[str] | None = None,
    optimization_run_id: int | None = None,
) -> int:
    """Persist the keyword intent inputs/outputs used for a run.

    This is intentionally stored as JSON arrays to preserve keyword phrases exactly.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO keyword_intent_snapshots (
            master_sku,
            item_group_id,
            item_ids_json,
            external_keywords_json,
            keyword_intent_master_json,
            optimization_run_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            item_group_id,
            json.dumps(item_ids) if item_ids else None,
            json.dumps(external_keywords) if external_keywords else None,
            json.dumps(keyword_intent_master) if keyword_intent_master else None,
            optimization_run_id,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id
