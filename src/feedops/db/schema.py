"""SQLite database schema and operations."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _rename_column_safe(conn, table, old_name, new_name):
    """Rename a column if the old name exists. No-op if already renamed."""
    try:
        conn.execute(f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}")
    except sqlite3.OperationalError:
        pass


def _add_column_safe(conn, table, column, col_type):
    """Add a column if it doesn't already exist."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass


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

    # Variant-level index (keyed by GMC offer_id) built from Product Catalog.csv.
    # This lets us resolve Shopify/GMC IDs even when Shopify cache is missing.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS variant_index (
            gmc_id TEXT PRIMARY KEY,
            master_sku TEXT NOT NULL,
            master_sku_norm TEXT NOT NULL,
            option_sku TEXT,
            option_sku_norm TEXT,
            core_sku TEXT,
            shopify_product_id TEXT,
            shopify_variant_id TEXT,

            -- Finish info from catalog
            finish TEXT,
            finish_code TEXT,

            -- Dimensions (kept as raw text to preserve units/format)
            product_length TEXT,
            product_width TEXT,
            product_height TEXT,
            projection TEXT,
            center_to_center TEXT,
            diameter TEXT,
            product_weight TEXT,

            -- Optional descriptive fields from catalog
            category TEXT,
            collection TEXT,
            material TEXT,

            updated_at TEXT NOT NULL
        )
    """
    )

    # Migrate: add finish columns to existing variant_index tables
    _add_column_safe(conn, "variant_index", "finish", "TEXT")
    _add_column_safe(conn, "variant_index", "finish_code", "TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_ingest_state (
            source_path TEXT PRIMARY KEY,
            source_mtime REAL NOT NULL,
            ingested_at TEXT NOT NULL
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

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_variant_index_master_norm
        ON variant_index(master_sku_norm)
    """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_variant_index_shopify_product
        ON variant_index(shopify_product_id)
    """
    )

    # Publish events table for tracking content deployments
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            platform TEXT NOT NULL,
            environment TEXT NOT NULL,
            action TEXT NOT NULL,
            patch_file TEXT NOT NULL,
            quality_score REAL,
            approval_status TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            published_at TEXT NOT NULL,
            published_by TEXT,
            rollback_id INTEGER,
            FOREIGN KEY (rollback_id) REFERENCES publish_events(id)
        )
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_sku_platform
        ON publish_events(master_sku, platform, published_at DESC)
    """
    )

    # Migration: Add batch and category columns to publish_events
    for column, col_type in [
        ("batch_id", "TEXT"),
        ("product_category", "TEXT"),
        ("product_collection", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE publish_events ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_batch
        ON publish_events(batch_id, published_at DESC)
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_category
        ON publish_events(product_category, published_at DESC)
    """
    )

    # Performance snapshots table for tracking metrics over time
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS performance_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            platform TEXT NOT NULL,
            environment TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            
            -- Traffic metrics
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0.0,
            
            -- Conversion metrics
            conversions INTEGER DEFAULT 0,
            conversion_value REAL DEFAULT 0.0,
            cvr REAL DEFAULT 0.0,
            
            -- Cost metrics
            cost REAL DEFAULT 0.0,
            cpc REAL DEFAULT 0.0,
            roas REAL DEFAULT 0.0,
            
            -- Content tracking
            publish_event_id INTEGER,
            content_version TEXT,
            days_since_publish INTEGER,
            
            fetched_at TEXT NOT NULL,
            FOREIGN KEY (publish_event_id) REFERENCES publish_events(id)
        )
    """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_snapshots_sku_platform_date
        ON performance_snapshots(master_sku, platform, snapshot_date DESC)
    """
    )

    # Performance baselines table for storing pre-FeedOps metrics
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS performance_baselines (
            master_sku TEXT NOT NULL,
            platform TEXT NOT NULL,
            baseline_start_date TEXT NOT NULL,
            baseline_end_date TEXT NOT NULL,
            
            avg_impressions REAL,
            avg_clicks REAL,
            avg_ctr REAL,
            avg_conversions REAL,
            avg_conversion_value REAL,
            avg_cvr REAL,
            avg_cost REAL,
            avg_roas REAL,
            
            created_at TEXT NOT NULL,
            PRIMARY KEY (master_sku, platform)
        )
    """
    )

    # SKU approvals table for element-level approval tracking
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sku_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL UNIQUE,

            -- Element-level approvals (NULL = not reviewed, 1 = approved, 0 = rejected)
            title_approved INTEGER,
            description_approved INTEGER,
            image_approved INTEGER,
            selected_finish TEXT,
            selected_image_index INTEGER,

            -- Overall state
            approval_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,

            -- Metadata
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """
    )

    # Migrate old column names to new ones for existing databases
    _rename_column_safe(conn, "sku_approvals", "status", "approval_status")
    _rename_column_safe(conn, "sku_approvals", "reviewed_by", "approved_by")
    _rename_column_safe(conn, "sku_approvals", "reviewed_at", "approved_at")
    _rename_column_safe(conn, "sku_approvals", "revision_notes", "notes")

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_approvals_status
        ON sku_approvals(approval_status, updated_at DESC)
    """
    )

    # Publish batches table for batch/cohort tracking
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            name TEXT,
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending',

            notes TEXT,

            created_at TEXT NOT NULL,
            executed_at TEXT,

            sku_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0
        )
    """
    )

    # Migrate old column names to new ones for existing databases
    _rename_column_safe(conn, "publish_batches", "batch_label", "name")
    _rename_column_safe(conn, "publish_batches", "published_at", "executed_at")
    _rename_column_safe(conn, "publish_batches", "selection_criteria", "notes")

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_batches_status
        ON publish_batches(status, created_at DESC)
    """
    )

    # Batch SKU assignments table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS batch_sku_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            master_sku TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(batch_id, master_sku),
            FOREIGN KEY (batch_id) REFERENCES publish_batches(batch_id)
        )
    """
    )

    # Migrate old column name for existing databases
    _rename_column_safe(conn, "batch_sku_assignments", "assigned_at", "created_at")

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_batch_assignments
        ON batch_sku_assignments(batch_id, master_sku)
    """
    )

    # Variant-level approvals (per-finish approval tracking)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS variant_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_sku TEXT NOT NULL,
            finish TEXT NOT NULL,
            finish_code TEXT,
            title_approved INTEGER,
            description_approved INTEGER,
            image_approved INTEGER,
            selected_image_index INTEGER,
            approval_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            approved_by TEXT,
            approved_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(master_sku, finish)
        )
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


def _normalize_master_sku(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    raw = "".join(raw.split())
    raw = raw.replace("/", "-")
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw.strip("-")


def _offer_ids_from_variant_index(db_path: Path, master_sku: str) -> list[str]:
    norm = _normalize_master_sku(master_sku)
    if not norm or not db_path.exists():
        return []
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT gmc_id FROM variant_index WHERE master_sku_norm = ?",
            (norm,),
        ).fetchall()
    finally:
        conn.close()
    return [row["gmc_id"] for row in rows if row and row["gmc_id"]]


def get_cached_merchant_center_items(
    master_sku: str, max_age_hours: float = 24.0
) -> list[dict]:
    """Retrieve cached Google Merchant Center items for a master SKU."""
    db_path = _resolve_db_path()
    offer_ids: list[str] = []
    shopify_payload = get_cached_shopify_product(
        master_sku, max_age_hours=max_age_hours
    )
    if shopify_payload:
        offer_ids = _derive_gmc_ids(shopify_payload)
    if not offer_ids:
        offer_ids = _offer_ids_from_variant_index(db_path, master_sku)
    if not offer_ids or not db_path.exists():
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


def log_publish_event(
    db_path: Path | str,
    *,
    master_sku: str,
    platform: str,
    environment: str,
    action: str,
    patch_file: str,
    status: str,
    quality_score: float | None = None,
    approval_status: str | None = None,
    error_message: str | None = None,
    published_by: str | None = None,
    rollback_id: int | None = None,
    batch_id: str | None = None,
    product_category: str | None = None,
    product_collection: str | None = None,
) -> int:
    """Log a publish or rollback event to the database.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU being published.
        platform: Target platform ('google', 'bing', 'shopify').
        environment: Deployment environment ('staging', 'production').
        action: Action type ('publish', 'rollback').
        patch_file: Path to the patch file used.
        status: Result status ('success', 'failed', 'pending').
        quality_score: Optional quality score from patch metadata.
        approval_status: Optional approval status from patch metadata.
        error_message: Optional error message if failed.
        published_by: Optional identifier for who triggered the publish.
        rollback_id: Optional reference to the publish event being rolled back.
        batch_id: Optional batch ID for batch tracking.
        product_category: Optional product category for analytics.
        product_collection: Optional product collection for analytics.

    Returns:
        ID of the inserted row.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO publish_events (
            master_sku, platform, environment, action, patch_file,
            quality_score, approval_status, status, error_message,
            published_at, published_by, rollback_id,
            batch_id, product_category, product_collection
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            platform,
            environment,
            action,
            patch_file,
            quality_score,
            approval_status,
            status,
            error_message,
            datetime.now(timezone.utc).isoformat(),
            published_by or "cli",
            rollback_id,
            batch_id,
            product_category,
            product_collection,
        ),
    )
    conn.commit()
    event_id = cursor.lastrowid
    conn.close()
    return event_id


def get_publish_history(
    db_path: Path | str,
    *,
    master_sku: str | None = None,
    platform: str | None = None,
    environment: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve publish event history from the database.

    Args:
        db_path: Path to database file.
        master_sku: Optional filter by SKU.
        platform: Optional filter by platform.
        environment: Optional filter by environment ('staging', 'production').
        limit: Maximum number of records to return.

    Returns:
        List of publish event dictionaries, most recent first.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)

    # Build query with optional filters
    query = "SELECT * FROM publish_events WHERE 1=1"
    params: list = []

    if master_sku:
        query += " AND master_sku = ?"
        params.append(master_sku)

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    if environment:
        query += " AND environment = ?"
        params.append(environment)

    query += " ORDER BY published_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        result_dict = {
            "id": row["id"],
            "master_sku": row["master_sku"],
            "platform": row["platform"],
            "environment": row["environment"],
            "action": row["action"],
            "patch_file": row["patch_file"],
            "quality_score": row["quality_score"],
            "approval_status": row["approval_status"],
            "status": row["status"],
            "error_message": row["error_message"],
            "published_at": row["published_at"],
            "published_by": row["published_by"],
            "rollback_id": row["rollback_id"],
        }
        # Add new columns (may not exist in older databases)
        try:
            result_dict["batch_id"] = row["batch_id"]
            result_dict["product_category"] = row["product_category"]
            result_dict["product_collection"] = row["product_collection"]
        except (KeyError, IndexError):
            result_dict["batch_id"] = None
            result_dict["product_category"] = None
            result_dict["product_collection"] = None
        results.append(result_dict)
    return results


def get_last_publish_event(
    db_path: Path | str,
    *,
    master_sku: str,
    platform: str,
) -> dict | None:
    """Get the most recent publish event for a SKU/platform combination.

    Args:
        db_path: Path to database file.
        master_sku: SKU to look up.
        platform: Platform to look up.

    Returns:
        Most recent publish event dict, or None if not found.
    """
    history = get_publish_history(
        db_path, master_sku=master_sku, platform=platform, limit=1
    )
    return history[0] if history else None


# Performance tracking functions


def save_performance_snapshot(
    db_path: Path | str,
    *,
    master_sku: str,
    platform: str,
    environment: str,
    snapshot_date: str,
    impressions: int = 0,
    clicks: int = 0,
    ctr: float = 0.0,
    conversions: int = 0,
    conversion_value: float = 0.0,
    cvr: float = 0.0,
    cost: float = 0.0,
    cpc: float = 0.0,
    roas: float = 0.0,
    publish_event_id: int | None = None,
    content_version: str | None = None,
    days_since_publish: int | None = None,
) -> int:
    """Save a performance snapshot to the database.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.
        platform: Platform ('google', 'bing', 'shopify').
        environment: Environment ('staging', 'production').
        snapshot_date: Date of metrics in YYYY-MM-DD format.
        impressions: Number of impressions.
        clicks: Number of clicks.
        ctr: Click-through rate (0.0 to 1.0).
        conversions: Number of conversions.
        conversion_value: Total conversion value.
        cvr: Conversion rate (0.0 to 1.0).
        cost: Total ad spend.
        cpc: Cost per click.
        roas: Return on ad spend.
        publish_event_id: Optional link to publish event.
        content_version: Content version ('original', 'feedops-v1', etc.).
        days_since_publish: Days since content was published.

    Returns:
        ID of the inserted row.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.execute(
        """
        INSERT INTO performance_snapshots (
            master_sku, platform, environment, snapshot_date,
            impressions, clicks, ctr, conversions, conversion_value, cvr,
            cost, cpc, roas, publish_event_id, content_version,
            days_since_publish, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            platform,
            environment,
            snapshot_date,
            impressions,
            clicks,
            ctr,
            conversions,
            conversion_value,
            cvr,
            cost,
            cpc,
            roas,
            publish_event_id,
            content_version,
            days_since_publish,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    snapshot_id = cursor.lastrowid
    conn.close()
    return snapshot_id


def get_performance_snapshots(
    db_path: Path | str,
    *,
    master_sku: str | None = None,
    platform: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Retrieve performance snapshots from the database.

    Args:
        db_path: Path to database file.
        master_sku: Optional filter by SKU.
        platform: Optional filter by platform.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).
        limit: Maximum number of records to return.

    Returns:
        List of snapshot dictionaries, most recent first.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)

    query = "SELECT * FROM performance_snapshots WHERE 1=1"
    params: list = []

    if master_sku:
        query += " AND master_sku = ?"
        params.append(master_sku)

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    if start_date:
        query += " AND snapshot_date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND snapshot_date <= ?"
        params.append(end_date)

    query += " ORDER BY snapshot_date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "master_sku": row["master_sku"],
                "platform": row["platform"],
                "environment": row["environment"],
                "snapshot_date": row["snapshot_date"],
                "impressions": row["impressions"],
                "clicks": row["clicks"],
                "ctr": row["ctr"],
                "conversions": row["conversions"],
                "conversion_value": row["conversion_value"],
                "cvr": row["cvr"],
                "cost": row["cost"],
                "cpc": row["cpc"],
                "roas": row["roas"],
                "publish_event_id": row["publish_event_id"],
                "content_version": row["content_version"],
                "days_since_publish": row["days_since_publish"],
                "fetched_at": row["fetched_at"],
            }
        )
    return results


def save_performance_baseline(
    db_path: Path | str,
    *,
    master_sku: str,
    platform: str,
    baseline_start_date: str,
    baseline_end_date: str,
    avg_impressions: float | None = None,
    avg_clicks: float | None = None,
    avg_ctr: float | None = None,
    avg_conversions: float | None = None,
    avg_conversion_value: float | None = None,
    avg_cvr: float | None = None,
    avg_cost: float | None = None,
    avg_roas: float | None = None,
) -> None:
    """Save or update a performance baseline.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.
        platform: Platform ('google', 'bing', 'shopify').
        baseline_start_date: Start of baseline period (YYYY-MM-DD).
        baseline_end_date: End of baseline period (YYYY-MM-DD).
        avg_impressions: Average daily impressions.
        avg_clicks: Average daily clicks.
        avg_ctr: Average CTR.
        avg_conversions: Average daily conversions.
        avg_conversion_value: Average daily conversion value.
        avg_cvr: Average CVR.
        avg_cost: Average daily cost.
        avg_roas: Average ROAS.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO performance_baselines (
            master_sku, platform, baseline_start_date, baseline_end_date,
            avg_impressions, avg_clicks, avg_ctr, avg_conversions,
            avg_conversion_value, avg_cvr, avg_cost, avg_roas, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_sku,
            platform,
            baseline_start_date,
            baseline_end_date,
            avg_impressions,
            avg_clicks,
            avg_ctr,
            avg_conversions,
            avg_conversion_value,
            avg_cvr,
            avg_cost,
            avg_roas,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_performance_baseline(
    db_path: Path | str,
    *,
    master_sku: str,
    platform: str,
) -> dict | None:
    """Retrieve a performance baseline for a SKU/platform combination.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.
        platform: Platform ('google', 'bing', 'shopify').

    Returns:
        Baseline dict or None if not found.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    conn = get_connection(db_path)
    row = conn.execute(
        """
        SELECT * FROM performance_baselines
        WHERE master_sku = ? AND platform = ?
        """,
        (master_sku, platform),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "master_sku": row["master_sku"],
        "platform": row["platform"],
        "baseline_start_date": row["baseline_start_date"],
        "baseline_end_date": row["baseline_end_date"],
        "avg_impressions": row["avg_impressions"],
        "avg_clicks": row["avg_clicks"],
        "avg_ctr": row["avg_ctr"],
        "avg_conversions": row["avg_conversions"],
        "avg_conversion_value": row["avg_conversion_value"],
        "avg_cvr": row["avg_cvr"],
        "avg_cost": row["avg_cost"],
        "avg_roas": row["avg_roas"],
        "created_at": row["created_at"],
    }


def get_published_skus_for_review(
    db_path: Path | str,
    *,
    platform: str,
    min_days_since_publish: int = 14,
    environment: str | None = None,
) -> list[dict]:
    """Get SKUs that have been published and are ready for performance review.

    Args:
        db_path: Path to database file.
        platform: Platform to filter by.
        min_days_since_publish: Minimum days since publish for statistical significance.
        environment: Optional environment filter.

    Returns:
        List of publish event dicts for SKUs ready for review.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)

    query = """
        SELECT * FROM publish_events
        WHERE platform = ?
          AND action = 'publish'
          AND status = 'success'
          AND julianday('now') - julianday(published_at) >= ?
    """
    params: list = [platform, min_days_since_publish]

    if environment:
        query += " AND environment = ?"
        params.append(environment)

    query += " ORDER BY published_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results: list[dict] = []
    for row in rows:
        result_dict = {
            "id": row["id"],
            "master_sku": row["master_sku"],
            "platform": row["platform"],
            "environment": row["environment"],
            "action": row["action"],
            "patch_file": row["patch_file"],
            "quality_score": row["quality_score"],
            "approval_status": row["approval_status"],
            "status": row["status"],
            "published_at": row["published_at"],
            "published_by": row["published_by"],
        }
        # Add new columns (may not exist in older databases)
        try:
            result_dict["batch_id"] = row["batch_id"]
            result_dict["product_category"] = row["product_category"]
            result_dict["product_collection"] = row["product_collection"]
        except (KeyError, IndexError):
            result_dict["batch_id"] = None
            result_dict["product_category"] = None
            result_dict["product_collection"] = None
        results.append(result_dict)
    return results


# SKU Approval functions


def save_sku_approval(
    db_path: Path | str,
    *,
    master_sku: str,
    title_approved: bool | None = None,
    description_approved: bool | None = None,
    image_approved: bool | None = None,
    selected_finish: str | None = None,
    selected_image_index: int | None = None,
    status: str = "pending",
    notes: str | None = None,
    approved_by: str | None = None,
) -> int:
    """Save or update a SKU approval record.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU being reviewed.
        title_approved: Whether title is approved (None=not reviewed, True/False).
        description_approved: Whether description is approved.
        image_approved: Whether lifestyle image is approved.
        selected_finish: Which finish variant the image was approved for.
        selected_image_index: Which lifestyle image was selected (0-based).
        status: Overall status ('pending', 'approved', 'revision', 'rejected').
        notes: Notes explaining why revision is needed.
        approved_by: Who performed the review.

    Returns:
        ID of the approval record.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)

    now = datetime.now(timezone.utc).isoformat()

    # Convert booleans to integers for SQLite
    title_int = 1 if title_approved else (0 if title_approved is False else None)
    desc_int = (
        1 if description_approved else (0 if description_approved is False else None)
    )
    image_int = 1 if image_approved else (0 if image_approved is False else None)

    # Auto-derive overall status from element-level approvals
    if status == "pending":
        if title_approved and description_approved and image_approved:
            status = "approved"
        elif (
            title_approved is False
            or description_approved is False
            or image_approved is False
        ):
            status = "rejected"

    # Check if record exists
    existing = conn.execute(
        "SELECT id FROM sku_approvals WHERE master_sku = ?",
        (master_sku,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE sku_approvals SET
                title_approved = ?,
                description_approved = ?,
                image_approved = ?,
                selected_finish = ?,
                selected_image_index = ?,
                approval_status = ?,
                notes = ?,
                approved_by = ?,
                approved_at = ?,
                updated_at = ?
            WHERE master_sku = ?
            """,
            (
                title_int,
                desc_int,
                image_int,
                selected_finish,
                selected_image_index,
                status,
                notes,
                approved_by,
                now,
                now,
                master_sku,
            ),
        )
        record_id = existing["id"]
    else:
        cursor = conn.execute(
            """
            INSERT INTO sku_approvals (
                master_sku, title_approved, description_approved, image_approved,
                selected_finish, selected_image_index, approval_status, notes,
                approved_by, approved_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                master_sku,
                title_int,
                desc_int,
                image_int,
                selected_finish,
                selected_image_index,
                status,
                notes,
                approved_by,
                now,
                now,
                now,
            ),
        )
        record_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return record_id


def get_sku_approval(
    db_path: Path | str,
    *,
    master_sku: str,
) -> dict | None:
    """Get approval state for a SKU.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU to look up.

    Returns:
        Approval dict or None if not found.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM sku_approvals WHERE master_sku = ?",
        (master_sku,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "master_sku": row["master_sku"],
        "title_approved": (
            row["title_approved"] == 1 if row["title_approved"] is not None else None
        ),
        "description_approved": (
            row["description_approved"] == 1
            if row["description_approved"] is not None
            else None
        ),
        "image_approved": (
            row["image_approved"] == 1 if row["image_approved"] is not None else None
        ),
        "selected_finish": row["selected_finish"],
        "selected_image_index": row["selected_image_index"],
        "approval_status": row["approval_status"],
        "notes": row["notes"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_pending_approvals(
    db_path: Path | str,
    *,
    limit: int = 100,
) -> list[dict]:
    """Get SKUs awaiting review (pending status).

    Args:
        db_path: Path to database file.
        limit: Maximum number of records to return.

    Returns:
        List of approval dicts with pending status.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT * FROM sku_approvals
        WHERE approval_status = 'pending'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    return [_row_to_approval_dict(row) for row in rows]


def get_revision_queue(
    db_path: Path | str,
    *,
    limit: int = 100,
) -> list[dict]:
    """Get SKUs flagged for revision.

    Args:
        db_path: Path to database file.
        limit: Maximum number of records to return.

    Returns:
        List of approval dicts with revision status.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT * FROM sku_approvals
        WHERE approval_status = 'revision'
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    return [_row_to_approval_dict(row) for row in rows]


def get_approved_for_batch(
    db_path: Path | str,
    *,
    exclude_batched: bool = True,
    limit: int = 500,
) -> list[dict]:
    """Get approved SKUs ready for batching.

    Args:
        db_path: Path to database file.
        exclude_batched: If True, exclude SKUs already assigned to a batch.
        limit: Maximum number of records to return.

    Returns:
        List of approval dicts with approved status.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)

    if exclude_batched:
        query = """
            SELECT sa.* FROM sku_approvals sa
            LEFT JOIN batch_sku_assignments bsa ON sa.master_sku = bsa.master_sku
            WHERE sa.approval_status = 'approved'
              AND bsa.id IS NULL
            ORDER BY sa.updated_at ASC
            LIMIT ?
        """
    else:
        query = """
            SELECT * FROM sku_approvals
            WHERE approval_status = 'approved'
            ORDER BY updated_at ASC
            LIMIT ?
        """

    rows = conn.execute(query, (limit,)).fetchall()
    conn.close()

    return [_row_to_approval_dict(row) for row in rows]


def _row_to_approval_dict(row) -> dict:
    """Convert a database row to an approval dict."""
    return {
        "id": row["id"],
        "master_sku": row["master_sku"],
        "title_approved": (
            row["title_approved"] == 1 if row["title_approved"] is not None else None
        ),
        "description_approved": (
            row["description_approved"] == 1
            if row["description_approved"] is not None
            else None
        ),
        "image_approved": (
            row["image_approved"] == 1 if row["image_approved"] is not None else None
        ),
        "selected_finish": row["selected_finish"],
        "selected_image_index": row["selected_image_index"],
        "approval_status": row["approval_status"],
        "notes": row["notes"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# Batch management functions


def create_batch(
    db_path: Path | str,
    *,
    batch_label: str | None = None,
    target_date: str | None = None,
    notes: dict | str | None = None,
    skus: list[str] | None = None,
    # Legacy alias
    selection_criteria: dict | None = None,
) -> str:
    """Create a new publish batch.

    Args:
        db_path: Path to database file.
        batch_label: Optional custom label for the batch.
        target_date: Planned publish date (YYYY-MM-DD).
        notes: Optional notes (JSON-serializable dict or string).
        skus: Optional list of SKUs to immediately assign to this batch.
        selection_criteria: Legacy alias for notes.

    Returns:
        The generated batch_id.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Generate unique batch ID
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM publish_batches WHERE batch_id LIKE ?",
        (f"Batch-{date_str}-%",),
    ).fetchone()
    seq = (existing["cnt"] or 0) + 1
    batch_id = f"Batch-{date_str}-{seq:03d}"

    # Resolve notes from either param
    resolved_notes = notes or selection_criteria
    notes_str = json.dumps(resolved_notes) if isinstance(resolved_notes, dict) else resolved_notes

    conn.execute(
        """
        INSERT INTO publish_batches (
            batch_id, name, target_date, status,
            notes, created_at, sku_count
        ) VALUES (?, ?, ?, 'pending', ?, ?, ?)
        """,
        (
            batch_id,
            batch_label,
            target_date,
            notes_str,
            now.isoformat(),
            len(skus) if skus else 0,
        ),
    )

    # Assign SKUs if provided
    if skus:
        for sku in skus:
            conn.execute(
                """
                INSERT OR IGNORE INTO batch_sku_assignments (
                    batch_id, master_sku, created_at
                ) VALUES (?, ?, ?)
                """,
                (batch_id, sku, now.isoformat()),
            )

    conn.commit()
    conn.close()
    return batch_id


def get_batch(
    db_path: Path | str,
    *,
    batch_id: str,
) -> dict | None:
    """Get batch details by ID.

    Args:
        db_path: Path to database file.
        batch_id: The batch ID to look up.

    Returns:
        Batch dict or None if not found.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM publish_batches WHERE batch_id = ?",
        (batch_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "name": row["name"],
        "target_date": row["target_date"],
        "status": row["status"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "executed_at": row["executed_at"],
        "sku_count": row["sku_count"],
        "success_count": row["success_count"],
        "failed_count": row["failed_count"],
    }


def get_all_batches(
    db_path: Path | str,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get all batches, optionally filtered by status.

    Args:
        db_path: Path to database file.
        status: Optional status filter.
        limit: Maximum number of records to return.

    Returns:
        List of batch dicts.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)

    if status:
        rows = conn.execute(
            """
            SELECT * FROM publish_batches
            WHERE status = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM publish_batches
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    conn.close()

    results = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "batch_id": row["batch_id"],
                "name": row["name"],
                "target_date": row["target_date"],
                "status": row["status"],
                "notes": row["notes"],
                "created_at": row["created_at"],
                "executed_at": row["executed_at"],
                "sku_count": row["sku_count"],
                "success_count": row["success_count"],
                "failed_count": row["failed_count"],
            }
        )
    return results


def assign_skus_to_batch(
    db_path: Path | str,
    *,
    batch_id: str,
    skus: list[str],
) -> int:
    """Assign SKUs to a batch.

    Args:
        db_path: Path to database file.
        batch_id: The batch to assign to.
        skus: List of MasterSKUs to assign.

    Returns:
        Number of SKUs assigned.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)

    now = datetime.now(timezone.utc).isoformat()
    assigned = 0

    for sku in skus:
        try:
            conn.execute(
                """
                INSERT INTO batch_sku_assignments (
                    batch_id, master_sku, created_at
                ) VALUES (?, ?, ?)
                """,
                (batch_id, sku, now),
            )
            assigned += 1
        except sqlite3.IntegrityError:
            # Already assigned
            pass

    # Update batch SKU count
    conn.execute(
        """
        UPDATE publish_batches SET sku_count = (
            SELECT COUNT(*) FROM batch_sku_assignments WHERE batch_id = ?
        ) WHERE batch_id = ?
        """,
        (batch_id, batch_id),
    )

    conn.commit()
    conn.close()
    return assigned


def get_batch_skus(
    db_path: Path | str,
    *,
    batch_id: str,
) -> list[str]:
    """Get all SKUs assigned to a batch.

    Args:
        db_path: Path to database file.
        batch_id: The batch to look up.

    Returns:
        List of MasterSKUs in the batch.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)
    rows = conn.execute(
        """
        SELECT master_sku FROM batch_sku_assignments
        WHERE batch_id = ?
        ORDER BY created_at
        """,
        (batch_id,),
    ).fetchall()
    conn.close()

    return [row["master_sku"] for row in rows]


def update_batch_status(
    db_path: Path | str,
    *,
    batch_id: str,
    status: str,
    success_count: int | None = None,
    failed_count: int | None = None,
) -> None:
    """Update batch status and counts.

    Args:
        db_path: Path to database file.
        batch_id: The batch to update.
        status: New status.
        success_count: Number of successful publishes.
        failed_count: Number of failed publishes.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return

    conn = get_connection(db_path)

    updates = ["status = ?"]
    params: list = [status]

    if status == "published":
        updates.append("executed_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())

    if success_count is not None:
        updates.append("success_count = ?")
        params.append(success_count)

    if failed_count is not None:
        updates.append("failed_count = ?")
        params.append(failed_count)

    params.append(batch_id)

    conn.execute(
        f"UPDATE publish_batches SET {', '.join(updates)} WHERE batch_id = ?",
        params,
    )
    conn.commit()
    conn.close()


# Published SKU tracking functions


def get_published_skus(
    db_path: Path | str,
    *,
    platform: str | None = None,
    environment: str = "production",
) -> set[str]:
    """Get set of SKUs that have been successfully published.

    Args:
        db_path: Path to database file.
        platform: Optional platform filter.
        environment: Environment filter (default: 'production').

    Returns:
        Set of MasterSKUs that have been published successfully.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return set()

    conn = get_connection(db_path)

    query = """
        SELECT DISTINCT master_sku FROM publish_events
        WHERE environment = ? AND status = 'success'
    """
    params: list = [environment]

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return {row["master_sku"] for row in rows}


def get_skus_needing_review(
    db_path: Path | str,
    *,
    all_skus: list[str],
    platform: str | None = None,
) -> list[str]:
    """Filter SKUs to only those not yet published to production.

    Args:
        db_path: Path to database file.
        all_skus: List of all candidate SKUs.
        platform: Optional platform filter.

    Returns:
        List of SKUs that haven't been published to production.
    """
    published = get_published_skus(db_path, platform=platform, environment="production")
    return [sku for sku in all_skus if sku not in published]


# Variant Approval functions


def save_variant_approval(
    db_path: Path | str,
    *,
    master_sku: str,
    finish: str,
    finish_code: str | None = None,
    title_approved: bool | None = None,
    description_approved: bool | None = None,
    image_approved: bool | None = None,
    selected_image_index: int | None = None,
    status: str = "pending",
    notes: str | None = None,
    approved_by: str | None = None,
) -> int:
    """Save or update a variant (per-finish) approval record.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.
        finish: The finish name (e.g., 'Polished Chrome').
        finish_code: Optional finish code.
        title_approved: Whether title is approved.
        description_approved: Whether description is approved.
        image_approved: Whether image is approved.
        selected_image_index: Which image was selected.
        status: Overall status.
        notes: Revision notes.
        approved_by: Who reviewed.

    Returns:
        ID of the approval record.
    """
    db_path = Path(db_path)
    init_db(db_path)
    conn = get_connection(db_path)

    now = datetime.now(timezone.utc).isoformat()

    title_int = 1 if title_approved else (0 if title_approved is False else None)
    desc_int = (
        1 if description_approved else (0 if description_approved is False else None)
    )
    image_int = 1 if image_approved else (0 if image_approved is False else None)

    # Auto-derive status
    if status == "pending":
        if title_approved and description_approved and image_approved:
            status = "approved"
        elif (
            title_approved is False
            or description_approved is False
            or image_approved is False
        ):
            status = "rejected"

    existing = conn.execute(
        "SELECT id FROM variant_approvals WHERE master_sku = ? AND finish = ?",
        (master_sku, finish),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE variant_approvals SET
                finish_code = ?,
                title_approved = ?,
                description_approved = ?,
                image_approved = ?,
                selected_image_index = ?,
                approval_status = ?,
                notes = ?,
                approved_by = ?,
                approved_at = ?,
                updated_at = ?
            WHERE master_sku = ? AND finish = ?
            """,
            (
                finish_code,
                title_int,
                desc_int,
                image_int,
                selected_image_index,
                status,
                notes,
                approved_by,
                now,
                now,
                master_sku,
                finish,
            ),
        )
        record_id = existing["id"]
    else:
        cursor = conn.execute(
            """
            INSERT INTO variant_approvals (
                master_sku, finish, finish_code,
                title_approved, description_approved, image_approved,
                selected_image_index, approval_status, notes,
                approved_by, approved_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                master_sku,
                finish,
                finish_code,
                title_int,
                desc_int,
                image_int,
                selected_image_index,
                status,
                notes,
                approved_by,
                now,
                now,
                now,
            ),
        )
        record_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return record_id


def get_variant_approval(
    db_path: Path | str,
    *,
    master_sku: str,
    finish: str,
) -> dict | None:
    """Get approval state for a specific variant (master_sku + finish).

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.
        finish: The finish name.

    Returns:
        Approval dict or None if not found.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM variant_approvals WHERE master_sku = ? AND finish = ?",
        (master_sku, finish),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "master_sku": row["master_sku"],
        "finish": row["finish"],
        "finish_code": row["finish_code"],
        "title_approved": (
            row["title_approved"] == 1 if row["title_approved"] is not None else None
        ),
        "description_approved": (
            row["description_approved"] == 1
            if row["description_approved"] is not None
            else None
        ),
        "image_approved": (
            row["image_approved"] == 1 if row["image_approved"] is not None else None
        ),
        "selected_image_index": row["selected_image_index"],
        "approval_status": row["approval_status"],
        "notes": row["notes"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_variant_approvals_for_sku(
    db_path: Path | str,
    *,
    master_sku: str,
) -> list[dict]:
    """Get all variant approvals for a given master SKU.

    Args:
        db_path: Path to database file.
        master_sku: The MasterSKU.

    Returns:
        List of variant approval dicts.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM variant_approvals WHERE master_sku = ? ORDER BY finish",
        (master_sku,),
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append(
            {
                "id": row["id"],
                "master_sku": row["master_sku"],
                "finish": row["finish"],
                "finish_code": row["finish_code"],
                "title_approved": (
                    row["title_approved"] == 1
                    if row["title_approved"] is not None
                    else None
                ),
                "description_approved": (
                    row["description_approved"] == 1
                    if row["description_approved"] is not None
                    else None
                ),
                "image_approved": (
                    row["image_approved"] == 1
                    if row["image_approved"] is not None
                    else None
                ),
                "selected_image_index": row["selected_image_index"],
                "approval_status": row["approval_status"],
                "notes": row["notes"],
                "approved_by": row["approved_by"],
                "approved_at": row["approved_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return results
