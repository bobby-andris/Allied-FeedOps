"""Variant-level index built from the Product Catalog CSV.

This table is keyed by GMCID (offer_id) and provides a deterministic join key
across catalog → Shopify → Merchant Center even when Shopify cache misses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from feedops.db.schema import get_connection, init_db
from feedops.loaders.catalog import load_catalog
from feedops.models.variant import parse_gmcid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_sku(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if not raw:
        return ""
    raw = "".join(raw.split())
    raw = raw.replace("/", "-")
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw.strip("-")


@dataclass(frozen=True)
class IngestState:
    source_path: str
    source_mtime: float
    ingested_at: str


def get_catalog_ingest_state(db_path: Path, catalog_path: Path) -> IngestState | None:
    if not db_path.exists():
        return None
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT source_path, source_mtime, ingested_at FROM catalog_ingest_state WHERE source_path = ?",
            (str(catalog_path.resolve()),),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return IngestState(
        source_path=row["source_path"],
        source_mtime=float(row["source_mtime"]),
        ingested_at=row["ingested_at"],
    )


def ensure_variant_index(db_path: Path, catalog_path: Path) -> bool:
    """Ensure `variant_index` is built and up-to-date for the given catalog file.

    Returns True if the index was rebuilt, False if it was already current.
    """
    db_path = Path(db_path)
    catalog_path = Path(catalog_path)
    init_db(db_path)

    current_mtime = catalog_path.stat().st_mtime
    state = get_catalog_ingest_state(db_path, catalog_path)
    if state and abs(state.source_mtime - current_mtime) < 1e-6:
        return False

    build_variant_index(db_path, catalog_path)
    return True


def build_variant_index(
    db_path: Path,
    catalog_path: Path,
    *,
    limit_master_skus: Iterable[str] | None = None,
) -> None:
    """(Re)build the variant_index table from Product Catalog.csv."""
    db_path = Path(db_path)
    catalog_path = Path(catalog_path)
    init_db(db_path)

    df = load_catalog(catalog_path)
    if limit_master_skus:
        wanted = {normalize_sku(v) for v in limit_master_skus if normalize_sku(v)}
        if wanted:
            df = df[df["master_sku"].map(normalize_sku).isin(wanted)]

    rows_to_upsert: list[tuple] = []
    updated_at = _now_iso()
    for _, row in df.iterrows():
        gmc_id = (row.get("gmc_id") or "").strip()
        if not gmc_id:
            continue
        master_sku = (row.get("master_sku") or "").strip()
        option_sku = (row.get("option_sku") or "").strip()
        core_sku = (row.get("core_sku") or "").strip()
        product_id, variant_id = parse_gmcid(gmc_id)
        rows_to_upsert.append(
            (
                gmc_id,
                master_sku,
                normalize_sku(master_sku),
                option_sku or None,
                normalize_sku(option_sku) or None,
                core_sku or None,
                product_id,
                variant_id,
                (row.get("product_length") or "").strip() or None,
                (row.get("product_width") or "").strip() or None,
                (row.get("product_height") or "").strip() or None,
                (row.get("projection") or "").strip() or None,
                (row.get("center_to_center") or "").strip() or None,
                (row.get("diameter") or "").strip() or None,
                (row.get("product_weight") or "").strip() or None,
                (row.get("category") or "").strip() or None,
                (row.get("collection") or "").strip() or None,
                (row.get("material") or "").strip() or None,
                updated_at,
            )
        )

    source_path = str(catalog_path.resolve())
    source_mtime = float(catalog_path.stat().st_mtime)
    conn = get_connection(db_path)
    try:
        if limit_master_skus is None:
            conn.execute("DELETE FROM variant_index")
        conn.executemany(
            """
            INSERT OR REPLACE INTO variant_index (
                gmc_id,
                master_sku,
                master_sku_norm,
                option_sku,
                option_sku_norm,
                core_sku,
                shopify_product_id,
                shopify_variant_id,
                product_length,
                product_width,
                product_height,
                projection,
                center_to_center,
                diameter,
                product_weight,
                category,
                collection,
                material,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_upsert,
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO catalog_ingest_state (
                source_path, source_mtime, ingested_at
            ) VALUES (?, ?, ?)
            """,
            (source_path, source_mtime, _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def get_shopify_product_id_for_master_sku(db_path: Path, master_sku: str) -> str | None:
    """Return Shopify product_id for a master SKU from variant_index."""
    norm = normalize_sku(master_sku)
    if not norm:
        return None
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT shopify_product_id
            FROM variant_index
            WHERE master_sku_norm = ?
              AND shopify_product_id IS NOT NULL
            LIMIT 1
            """,
            (norm,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return row["shopify_product_id"]


def get_offer_ids_for_master_sku(db_path: Path, master_sku: str) -> list[str]:
    """Return all GMCIDs (offer_ids) for a master SKU from variant_index."""
    norm = normalize_sku(master_sku)
    if not norm:
        return []
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT gmc_id
            FROM variant_index
            WHERE master_sku_norm = ?
            """,
            (norm,),
        ).fetchall()
    finally:
        conn.close()
    return [r["gmc_id"] for r in rows if r and r["gmc_id"]]

