"""Master SKU alias normalization helpers for Supabase-backed flows."""

from __future__ import annotations

import itertools
import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)

_CANONICAL_TABLES: tuple[str, ...] = (
    "product_catalog",
    "variant_index",
    "generated_content",
    "variant_finish_sentences",
    "sku_approvals",
)


def _dedupe_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _separator_variants(value: str) -> list[str]:
    chars = list(value)
    separator_positions = [idx for idx, ch in enumerate(chars) if ch in "-/"]
    if not separator_positions:
        return [value]

    variants = [value]
    for combo in itertools.product("-/", repeat=len(separator_positions)):
        if all(chars[pos] == combo[idx] for idx, pos in enumerate(separator_positions)):
            continue
        candidate = chars.copy()
        for idx, pos in enumerate(separator_positions):
            candidate[pos] = combo[idx]
        variants.append("".join(candidate))
    return variants


def build_master_sku_aliases(master_sku: str) -> list[str]:
    """Generate separator-based alias candidates in preference order."""
    requested = "".join((master_sku or "").strip().split())
    if not requested:
        return []

    requested_upper = requested.upper()
    pool = _dedupe_preserve(
        [
            requested_upper,
            *_separator_variants(requested_upper),
            requested_upper.replace("/", ""),
            requested_upper.replace("-", ""),
        ]
    )

    def _distance(candidate: str) -> tuple[int, int]:
        mismatch_count = sum(
            1 for idx, ch in enumerate(candidate) if idx < len(requested_upper) and ch != requested_upper[idx]
        )
        return mismatch_count, abs(candidate.count("/") - requested_upper.count("/"))

    ordered = sorted(pool[1:], key=_distance)
    return [requested_upper, *ordered]


def _choose_best_alias(candidates: list[str], matches: list[str]) -> str | None:
    match_set = set(matches)
    for candidate in candidates:
        if candidate in match_set:
            return candidate
    return None


def _lookup_alias_match(supabase, table_name: str, aliases: list[str]) -> str | None:
    if not aliases:
        return None
    try:
        result = (
            supabase.table(table_name)
            .select("master_sku")
            .in_("master_sku", aliases)
            .limit(500)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - defensive for Supabase transport failures
        logger.warning("SKU alias lookup failed on %s: %s", table_name, exc)
        return None

    rows = getattr(result, "data", None) or []
    if not isinstance(rows, list) or not rows:
        return None

    table_matches = _dedupe_preserve(
        [
            (row.get("master_sku") or "").strip().upper()
            for row in rows
            if isinstance(row, dict)
        ]
    )
    return _choose_best_alias(aliases, table_matches)


def resolve_canonical_master_sku(
    supabase,
    master_sku: str,
    *,
    tables: Iterable[str] = _CANONICAL_TABLES,
) -> str:
    """Resolve a master SKU to canonical table-backed form when aliases exist."""
    aliases = build_master_sku_aliases(master_sku)
    if not aliases:
        return ""

    for table_name in tables:
        matched = _lookup_alias_match(supabase, table_name, aliases)
        if matched:
            return matched

    return aliases[0]


def resolve_canonical_master_skus(
    supabase,
    master_skus: Iterable[str],
    *,
    tables: Iterable[str] = _CANONICAL_TABLES,
) -> list[str]:
    """Resolve a batch of master SKUs to canonical forms."""
    return [
        resolve_canonical_master_sku(supabase, sku, tables=tables)
        for sku in master_skus
    ]
