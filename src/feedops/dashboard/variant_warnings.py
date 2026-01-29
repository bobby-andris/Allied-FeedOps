from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_variant_title_warnings(patches: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize variant title warning signals across patch exports.

    Warnings are emitted into patch JSON under `_meta.variant_title_warnings`.
    This helper is intentionally tolerant of missing/malformed data.
    """
    warning_counts: Counter[str] = Counter()
    patches_with_warnings = 0

    for patch in patches:
        warnings = ((patch or {}).get("_meta") or {}).get("variant_title_warnings") or []
        if not warnings:
            continue

        patches_with_warnings += 1
        for warning in warnings:
            normalized = (warning or "").lower()
            if "duplicate variant title" in normalized:
                warning_counts["duplicate"] += 1
            elif (
                "appears after the first" in normalized
                and "consider moving finish earlier" in normalized
            ):
                warning_counts["finish_after_visible_chars"] += 1
            else:
                warning_counts["other"] += 1

    return {
        "total_patches": len(patches),
        "patches_with_warnings": patches_with_warnings,
        "warning_counts": dict(warning_counts),
    }

