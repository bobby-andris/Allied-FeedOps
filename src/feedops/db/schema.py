"""SQLite database schema and operations."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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


def _resolve_db_path(db_path: Path | str | None = None) -> Path:
    if db_path:
        return Path(db_path)
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def init_db(db_path: Path | str) -> None:
    """Initialize database with required tables.

    Args:
        db_path: Path to database file.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)

    conn.execute(
        """
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
            data_source TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    conn.execute(
        """
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
    """
    )

    conn.execute(
        """
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
    """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS merchant_center_items (
            offer_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shopify_products (
            master_sku TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            ttl_hours REAL DEFAULT 24.0,
            UNIQUE(master_sku)
        )
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_runs_master_sku
        ON optimization_runs(master_sku)
    """
    )
    try:
        conn.execute("ALTER TABLE optimization_runs ADD COLUMN data_source TEXT")
    except sqlite3.OperationalError:
        pass

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_versions_master_sku
        ON content_versions(master_sku)
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_keyword_intent_master_sku
        ON keyword_intent_snapshots(master_sku)
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_merchant_center_offer
        ON merchant_center_items(offer_id)
    """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shopify_fetched
        ON shopify_products(fetched_at)
    """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_shopify_ttl
        ON shopify_products(master_sku, fetched_at, ttl_hours)
    """
    )

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
    data_source: str | None = None,
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
            approval_status, data_source, status, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data_source,
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


def upsert_merchant_center_items(db_path: Path | str, items: list[dict]) -> None:
    if not items:
        return
    conn = get_connection(db_path)
    payloads = []
    for item in items:
        offer_id = item.get("offerId")
        if not offer_id:
            continue
        fetched_at = item.get("fetched_at") or datetime.now().isoformat()
        payloads.append((offer_id, json.dumps(item), fetched_at))

    conn.executemany(
        """
        INSERT OR REPLACE INTO merchant_center_items (
            offer_id, payload_json, fetched_at
        ) VALUES (?, ?, ?)
        """,
        payloads,
    )
    conn.commit()
    conn.close()


def load_merchant_center_items(db_path: Path | str) -> dict[str, dict]:
    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT offer_id, payload_json FROM merchant_center_items"
    ).fetchall()
    conn.close()
    records: dict[str, dict] = {}
    for row in rows:
        payload = json.loads(row["payload_json"])
        records[row["offer_id"]] = payload
    return records


def cache_shopify_product(
    master_sku: str, product_id: str, payload: dict, ttl_hours: float = 24.0
) -> None:
    """Cache a Shopify product in the database."""
    db_path = _resolve_db_path()
    init_db(db_path)
    conn = get_connection(db_path)
    fetched_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO shopify_products (
            master_sku, product_id, payload_json, fetched_at, ttl_hours
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            product_id,
            json.dumps(payload),
            fetched_at,
            ttl_hours,
        ),
    )
    conn.commit()
    conn.close()


def get_cached_shopify_product(
    master_sku: str, max_age_hours: float = 24.0
) -> dict | None:
    """Retrieve cached Shopify product if not expired."""
    db_path = _resolve_db_path()
    if not db_path.exists():
        return None
    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT payload_json, fetched_at, ttl_hours
        FROM shopify_products
        WHERE master_sku = ?
        """,
        (master_sku,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    fetched_at = _parse_timestamp(row["fetched_at"])
    if not fetched_at:
        return None
    ttl_hours = row["ttl_hours"] if row["ttl_hours"] else max_age_hours
    max_age = min(max_age_hours, ttl_hours) if ttl_hours else max_age_hours
    age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
    if max_age <= 0 or age_hours > max_age:
        return None
    return json.loads(row["payload_json"])


def _parse_gid(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("/")
    if parts and parts[-1].isdigit():
        return parts[-1]
    return None


def _derive_gmc_ids(payload: dict) -> list[str]:
    product_id = payload.get("legacyResourceId") or _parse_gid(payload.get("id"))
    if not product_id:
        return []
    gmc_ids: list[str] = []
    variants = payload.get("variants", {}).get("nodes", []) or []
    for variant in variants:
        variant_id = variant.get("legacyResourceId") or _parse_gid(variant.get("id"))
        if variant_id:
            gmc_ids.append(f"shopify_US_{product_id}_{variant_id}")
    return gmc_ids


def get_cached_merchant_center_items(
    master_sku: str, max_age_hours: float = 24.0
) -> list[dict]:
    """Retrieve cached Google Merchant Center items for a master SKU."""
    shopify_payload = get_cached_shopify_product(
        master_sku, max_age_hours=max_age_hours
    )
    if not shopify_payload:
        return []
    offer_ids = _derive_gmc_ids(shopify_payload)
    if not offer_ids:
        return []

    db_path = _resolve_db_path()
    if not db_path.exists():
        return []
    placeholders = ", ".join("?" for _ in offer_ids)
    conn = get_connection(db_path)
    rows = conn.execute(
        f"""
        SELECT offer_id, payload_json, fetched_at
        FROM merchant_center_items
        WHERE offer_id IN ({placeholders})
        """,
        offer_ids,
    ).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        fetched_at = _parse_timestamp(row["fetched_at"])
        if not fetched_at:
            continue
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if max_age_hours <= 0 or age_hours > max_age_hours:
            continue
        results.append(json.loads(row["payload_json"]))
    return results
