"""Local keyword bank loader (for Apify/SEO research outputs).

This module intentionally reads from local disk (typically under data/ which is gitignored)
so teams can refresh keyword research without committing large or sensitive datasets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_KEYWORD_BANK_PATH = Path("data/keyword-bank.json")


def _keyword_bank_path() -> Path:
    override = os.getenv("FEEDOPS_KEYWORD_BANK_PATH")
    return Path(override) if override else DEFAULT_KEYWORD_BANK_PATH


def load_keyword_bank() -> dict[str, Any]:
    """Load keyword bank JSON if present; otherwise return empty dict."""
    path = _keyword_bank_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def get_external_keywords(
    category: str | None = None,
    master_sku: str | None = None,
) -> list[str]:
    """Return external keyword phrases for a MasterSKU (preferred) or category fallback.

    Expected file format (data/keyword-bank.json):
    {
      "<Category>": {
        "external_keywords": ["phrase 1", "phrase 2", ...]
      }
    }
    """
    bank = load_keyword_bank()
    if not isinstance(bank, dict):
        return []

    # Preferred: MasterSKU-specific keywords (allows intent tuning beyond category-level lists).
    if master_sku:
        master_obj = bank.get(master_sku)
        if isinstance(master_obj, dict):
            keywords = master_obj.get("external_keywords")
            if isinstance(keywords, list):
                return [str(k).strip() for k in keywords if str(k).strip()]

    # Fallback: category-level keywords (original behavior).
    if not category:
        return []
    category_obj = bank.get(category)
    if not isinstance(category_obj, dict):
        return []
    keywords = category_obj.get("external_keywords")
    if not isinstance(keywords, list):
        return []
    return [str(k).strip() for k in keywords if str(k).strip()]

