"""OfferId preflight helpers.

For Google Merchant Center supplemental feeds, publishing items whose `offerId`
does not exist in the Merchant Center snapshot results in silent failures or
misleading reporting. This module provides a lightweight gate against the local
MC snapshot table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def load_known_offer_ids(db_path: Path) -> set[str]:
    """Load known offer IDs from the merchant_center_items table."""
    db_path = Path(db_path)
    if not db_path.exists():
        return set()

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT offer_id FROM merchant_center_items")
        except sqlite3.OperationalError:
            return set()
        return {row[0] for row in cur.fetchall() if row and row[0]}
    finally:
        conn.close()


def filter_patches_by_offer_id(
    patches: list[dict[str, Any]],
    known_offer_ids: set[str],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Filter patches and variant items to only include known offer IDs."""
    filtered: list[dict[str, Any]] = []
    missing: set[str] = set()

    for patch in patches:
        offer_id = patch.get("offerId")
        if offer_id and offer_id not in known_offer_ids:
            missing.add(str(offer_id))
            continue

        new_patch = dict(patch)
        variants = patch.get("variants", [])
        if isinstance(variants, list):
            new_variants = []
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_offer_id = variant.get("offerId") or variant.get("gmc_id")
                if variant_offer_id and variant_offer_id not in known_offer_ids:
                    missing.add(str(variant_offer_id))
                    continue
                new_variants.append(dict(variant))
            new_patch["variants"] = new_variants

        filtered.append(new_patch)

    return filtered, missing

