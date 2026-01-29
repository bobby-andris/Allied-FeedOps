"""Collection description lookup for on-site merchandising.

Customer-facing collection language can improve perceived design value on Shopify,
but must be sanitized to avoid unverified, product-specific claims (e.g., exact
finish counts) that may not apply to every SKU.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path


_COLLECTION_DESCRIPTIONS_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "data"
    / "Collection_Descriptions_Complete_All_41_20260124.csv"
)

_AVAILABLE_IN_RE = re.compile(
    r"\bAvailable in\b.*?$",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_collection_descriptions() -> dict[str, dict[str, str]]:
    """Return mapping of normalized collection name -> row dict."""
    try:
        with _COLLECTION_DESCRIPTIONS_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = {}
            for row in reader:
                name = (row.get("Collection Name") or "").strip()
                if not name:
                    continue
                rows[name.casefold()] = {k: (v or "").strip() for k, v in row.items()}
            return rows
    except FileNotFoundError:
        return {}


def get_collection_description(collection_name: str | None) -> str | None:
    if not collection_name:
        return None
    row = _load_collection_descriptions().get(collection_name.casefold())
    if not row:
        return None
    description = (row.get("Description") or "").strip()
    return description or None


def is_known_collection_name(collection_name: str | None) -> bool:
    """Return True if the collection name exists in the curated 41-collection CSV."""
    if not collection_name:
        return False
    return collection_name.casefold() in _load_collection_descriptions()


def sanitize_collection_description(description: str) -> str:
    """Remove unverified, product-specific claims from a collection description."""
    text = (description or "").strip()
    if not text:
        return ""

    # Drop "Available in ..." clauses that may not match a specific SKU's variant set.
    text = _AVAILABLE_IN_RE.sub("", text).strip()

    # Trim trailing separators left by removal.
    text = text.rstrip("—-– ").strip()

    # Limit size for on-page scanning.
    max_len = 420
    if len(text) <= max_len:
        return text
    clipped = text[:max_len]
    if "." in clipped:
        clipped = clipped.rsplit(".", 1)[0] + "."
    return clipped.strip()
