"""Helpers for generating multi-size spec matrices from variant truth.

Shopify product descriptions (`body_html`) are product-level and cannot be
variant-specific without theme/metafield work. For the pilot we generate a
size/spec matrix from variant rows to avoid size-mismatched claims.

IMPORTANT: Avoid inferring "size" from SKU suffixes when real dimensions are
available. Many SKUs include series numbers (e.g., "MB-20") that are NOT inches.
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


def _as_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_dimension_present(parent_sku: ParentSKU) -> bool:
    for v in parent_sku.variants:
        if (
            _as_float(v.product_length) is not None
            or _as_float(v.product_width) is not None
            or _as_float(v.product_height) is not None
        ):
            return True
    return False


def _unique_dimension_values(parent_sku: ParentSKU, field: str) -> list[float]:
    values: set[float] = set()
    for v in parent_sku.variants:
        raw = getattr(v, field, None)
        num = _as_float(raw)
        if num is None:
            continue
        # Round to avoid float noise from CSV parsing.
        values.add(round(num, 3))
    return sorted(values)


def _choose_size_axis(parent_sku: ParentSKU) -> str | None:
    """Pick the dimension field that best represents "size" for a matrix.

    We prefer length when multiple distinct lengths exist. Otherwise choose the
    largest-magnitude varying dimension.
    """
    candidates = []
    for field in ("product_length", "product_width", "product_height"):
        values = _unique_dimension_values(parent_sku, field)
        if len(values) >= 2:
            candidates.append((field, values))

    if not candidates:
        return None

    for field, _values in candidates:
        if field == "product_length":
            return "product_length"

    # Choose dimension with the largest median value to avoid "2 inch" style
    # matrices for small fixed-size items.
    def _median(vals: list[float]) -> float:
        vals2 = sorted(vals)
        mid = len(vals2) // 2
        if len(vals2) % 2:
            return vals2[mid]
        return (vals2[mid - 1] + vals2[mid]) / 2

    candidates.sort(key=lambda item: _median(item[1]), reverse=True)
    return candidates[0][0]


def _variant_size_label_from_dimensions(
    parent_sku: ParentSKU, variant: Variant, field: str
) -> tuple[int, str] | None:
    raw = getattr(variant, field, None)
    num = _as_float(raw)
    if num is None:
        return None
    # Use integer inches when possible (typical for bars).
    if float(num).is_integer():
        size_int = int(num)
        if size_int <= 0:
            return None
        return size_int, f"{size_int} Inch"
    # Use rounded float inches for non-integer sizes.
    rounded = round(float(num), 3)
    if rounded <= 0:
        return None
    # Keep ordering stable by rounding to nearest thousandth and scaling.
    size_int = int(round(rounded * 1000))
    return size_int, f"{_format_number(rounded)} Inch"


def _is_plausible_sku_size(size_int: int, variant: Variant) -> bool:
    """Heuristic guardrail: reject SKU suffix numbers that are likely series ids.

    Many Allied Brass SKUs include a trailing number that is not a size in inches
    (e.g., "MB-20" or "SH-84"). When dimension truth is present, use it to sanity
    check the parsed SKU size.
    """
    dims: list[float] = []
    for raw in (
        variant.product_length,
        variant.product_width,
        variant.product_height,
        variant.projection,
    ):
        num = _as_float(raw)
        if num is None or num <= 0:
            continue
        dims.append(num)
    if not dims:
        return True
    max_dim = max(dims)

    # If the physical dimensions are small (<6") but SKU suffix is large (>=10"),
    # it's almost certainly a series number.
    if max_dim < 6 and size_int >= 10:
        return False

    delta = abs(max_dim - float(size_int))
    if delta <= 8:
        return True
    if size_int > 0 and (delta / float(size_int)) <= 0.30:
        return True
    return False


def _variant_size_label_from_sku(variant: Variant) -> tuple[int, str] | None:
    """Return (size_int, 'NN Inch') extracted from option_sku, or None.

    Fallback only when dimension truth is unavailable.
    """
    core = variant.option_sku
    if variant.finish_code and core.endswith(f"-{variant.finish_code}"):
        core = core[: -(len(variant.finish_code) + 1)]
    match = _TRAILING_SIZE_RE.search(core)
    if not match:
        return None
    size_int = int(match.group(1))
    if size_int <= 0 or size_int > 96:
        return None
    return size_int, f"{size_int} Inch"


def get_variant_size_label(variant: Variant) -> str | None:
    """Deprecated helper: size label inferred from SKU suffix.

    Prefer using build_size_matrix(), which is dimension-based when possible.
    """
    parsed = _variant_size_label_from_sku(variant)
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

    axis = None
    has_dims = _is_dimension_present(parent_sku)
    if has_dims:
        axis = _choose_size_axis(parent_sku)

    for variant in parent_sku.variants:
        parsed = _variant_size_label_from_sku(variant)
        if parsed and has_dims:
            size_int, _label = parsed
            if not _is_plausible_sku_size(size_int, variant):
                parsed = None

        if not parsed and axis:
            parsed = _variant_size_label_from_dimensions(parent_sku, variant, axis)
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
        parsed_label = _variant_size_label_from_sku(v)
        if parsed_label and has_dims:
            parsed_size_int, _label = parsed_label
            if not _is_plausible_sku_size(parsed_size_int, v):
                parsed_label = None

        if parsed_label:
            _size_int, size_label = parsed_label
        elif axis:
            _size_int, size_label = _variant_size_label_from_dimensions(
                parent_sku, v, axis
            ) or (size_int, f"{size_int} Inch")
        else:
            _size_int, size_label = (size_int, f"{size_int} Inch")
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
