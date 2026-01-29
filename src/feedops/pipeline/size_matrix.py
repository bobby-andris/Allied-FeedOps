"""Helpers for generating multi-size spec matrices from variant truth.

Shopify product descriptions (`body_html`) are product-level and cannot be
variant-specific without theme/metafield work. For the pilot we generate a
size/spec matrix from variant rows to avoid size-mismatched claims.
"""

from __future__ import annotations

import re
from typing import Any

from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant

_TRAILING_SIZE_RE = re.compile(r"[/-](\d+)$")


def _format_number(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    num = float(value)
    if num.is_integer():
        return str(int(num))
    return str(num).rstrip("0").rstrip(".")


def _variant_size_label(variant: Variant) -> tuple[int, str] | None:
    """Return (size_int, 'NN Inch') extracted from option_sku, or None."""
    core = variant.option_sku
    if variant.finish_code and core.endswith(f"-{variant.finish_code}"):
        core = core[: -(len(variant.finish_code) + 1)]
    match = _TRAILING_SIZE_RE.search(core)
    if not match:
        return None
    size_int = int(match.group(1))
    # Guard against series numbers like "-700" being misinterpreted as inches.
    if size_int <= 0 or size_int > 96:
        return None
    return size_int, f"{size_int} Inch"


def get_variant_size_label(variant: Variant) -> str | None:
    """Public helper for deriving a normalized size label from a Variant."""
    parsed = _variant_size_label(variant)
    if not parsed:
        return None
    _size_int, label = parsed
    return label


def _variant_completeness_score(variant: Variant) -> int:
    fields = [
        variant.product_length,
        variant.product_width,
        variant.product_height,
        variant.projection,
        variant.product_weight,
    ]
    return sum(1 for v in fields if v is not None)


def build_size_matrix(parent_sku: ParentSKU) -> list[dict[str, Any]]:
    """Build a size/spec matrix from variant-level dimensions.

    Returns one row per unique parsed size label.
    """
    best_by_size: dict[int, Variant] = {}
    for variant in parent_sku.variants:
        parsed = _variant_size_label(variant)
        if not parsed:
            continue
        size_int, _label = parsed
        existing = best_by_size.get(size_int)
        if not existing or _variant_completeness_score(variant) > _variant_completeness_score(
            existing
        ):
            best_by_size[size_int] = variant

    rows: list[dict[str, Any]] = []
    for size_int in sorted(best_by_size.keys()):
        v = best_by_size[size_int]
        _size_int, size_label = _variant_size_label(v) or (size_int, f"{size_int} Inch")
        length = _format_number(v.product_length)
        width = _format_number(v.product_width)
        height = _format_number(v.product_height)
        if length and width and height:
            overall = f"{length} × {width} × {height} in"
        elif length:
            overall = f"{length} in"
        else:
            overall = ""

        rows.append(
            {
                "size_int": size_int,
                "size_label": size_label,
                "overall": overall,
                "projection_in": _format_number(v.projection),
                "weight_lb": _format_number(v.product_weight),
            }
        )
    return rows
