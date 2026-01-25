"""Auto-extract verifiable claims from generated content."""
from __future__ import annotations

import html
import re
from typing import Iterable

from feedops.models import Candidate, ParentSKU, Claim


_NUMERIC_FIELDS = (
    "center_to_center",
    "diameter",
    "mirror_height",
    "mirror_width",
    "thickness",
    "product_length",
    "product_width",
    "product_height",
    "projection",
)

_MATERIAL_PHRASES = [
    "solid stainless steel",
    "stainless steel",
    "solid brass",
    "solid bronze",
    "brass",
    "bronze",
    "aluminum",
    "zinc",
    "ceramic",
    "glass",
]

_MATERIAL_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _MATERIAL_PHRASES) + r")\b",
    re.IGNORECASE,
)

_CAPACITY_PATTERNS = [
    re.compile(
        r"\b(?:supports? up to|support up to)\s*(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?:lb|lbs|pounds)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:weight capacity|capacity)\s*(?:is|:)?\s*(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?:lb|lbs|pounds)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds)\s*(?:capacity)\b",
        re.IGNORECASE,
    ),
]

_INCH_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?(?:\s*[- ]\s*\d+/\d+)?|\d+\s+\d+/\d+|\d+/\d+)\s*"
    r"(?:-\s*|\s*)?(?:\"|inch(?:es)?|in\b)",
    re.IGNORECASE,
)


def extract_claims(candidate: Candidate, parent_sku: ParentSKU) -> list[Claim]:
    """Extract verifiable claims from generated customer-facing text."""
    texts = _collect_candidate_text(candidate)
    finish_claims, finish_spans = _extract_finish_claims(texts, parent_sku)
    material_claims = _extract_material_claims(texts, finish_spans)
    capacity_claims = _extract_capacity_claims(texts)
    dimension_claims = _extract_dimension_claims(texts, parent_sku)
    return dedupe_claims(
        finish_claims + material_claims + capacity_claims + dimension_claims
    )


def dedupe_claims(claims: Iterable[Claim]) -> list[Claim]:
    """Dedupe claims by source_field and normalized source_value."""
    deduped: list[Claim] = []
    seen: set[tuple[str, str]] = set()
    for claim in claims:
        normalized = _normalize_claim_value(claim)
        key = (claim.source_field, normalized)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    return deduped


def _collect_candidate_text(candidate: Candidate) -> list[str]:
    """Collect customer-facing text fields for scanning."""
    texts = [
        candidate.google_title,
        candidate.google_short_title,
        candidate.google_description,
        candidate.bing_title,
        candidate.bing_description,
        candidate.shopify_title,
        _strip_html(candidate.shopify_description),
    ]
    return [_normalize_whitespace(t) for t in texts if t]


def _strip_html(text: str) -> str:
    if not text:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(stripped)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_finish_claims(
    texts: list[str],
    parent_sku: ParentSKU,
) -> tuple[list[Claim], list[list[tuple[int, int]]]]:
    finishes = sorted(
        {v.finish for v in parent_sku.variants if v.finish},
        key=len,
        reverse=True,
    )
    spans: list[list[tuple[int, int]]] = [[] for _ in texts]
    if not finishes:
        return [], spans

    pattern = re.compile(
        r"(?<!\w)(?:"
        + "|".join(re.escape(finish) for finish in finishes)
        + r")(?!\w)",
        re.IGNORECASE,
    )
    claims: list[Claim] = []
    for idx, text in enumerate(texts):
        for match in pattern.finditer(text):
            spans[idx].append(match.span())
            matched = match.group(0)
            claims.append(
                Claim(
                    claim=matched,
                    source_field="available_finishes",
                    source_value=matched,
                )
            )
    return claims, spans


def _extract_material_claims(
    texts: list[str],
    finish_spans: list[list[tuple[int, int]]],
) -> list[Claim]:
    claims: list[Claim] = []
    for idx, text in enumerate(texts):
        spans = finish_spans[idx] if idx < len(finish_spans) else []
        for match in _MATERIAL_REGEX.finditer(text):
            if _overlaps(match.span(), spans):
                continue
            matched = match.group(0)
            claims.append(
                Claim(
                    claim=matched,
                    source_field="material",
                    source_value=matched,
                )
            )
    return claims


def _extract_capacity_claims(texts: list[str]) -> list[Claim]:
    claims: list[Claim] = []
    for text in texts:
        for pattern in _CAPACITY_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group("value")
                normalized = f"{_format_number(float(value))} lb"
                claims.append(
                    Claim(
                        claim=match.group(0),
                        source_field="weight_capacity",
                        source_value=normalized,
                    )
                )
    return claims


def _extract_dimension_claims(texts: list[str], parent_sku: ParentSKU) -> list[Claim]:
    claims: list[Claim] = []
    dimension_values = _get_dimension_values(parent_sku)
    if not dimension_values:
        return claims
    for text in texts:
        for match in _INCH_PATTERN.finditer(text):
            parsed = _parse_number(match.group("value"))
            if parsed is None:
                continue
            field = _match_dimension_field(parsed, dimension_values)
            if not field:
                continue
            claims.append(
                Claim(
                    claim=match.group(0),
                    source_field=field,
                    source_value=f"{_format_number(parsed)} in",
                )
            )
    return claims


def _get_dimension_values(parent_sku: ParentSKU) -> dict[str, float]:
    values: dict[str, float] = {}
    for field in _NUMERIC_FIELDS:
        if hasattr(parent_sku, field):
            value = getattr(parent_sku, field)
            if value is not None:
                values[field] = float(value)
    if parent_sku.variants:
        variant = parent_sku.variants[0]
        for field in _NUMERIC_FIELDS:
            if field in values:
                continue
            if hasattr(variant, field):
                value = getattr(variant, field)
                if value is not None:
                    values[field] = float(value)
    return values


def _match_dimension_field(value: float, values: dict[str, float]) -> str | None:
    tolerance = 1e-3
    for field in _NUMERIC_FIELDS:
        if field not in values:
            continue
        if abs(values[field] - value) <= tolerance:
            return field
    return None


def _parse_number(raw: str) -> float | None:
    value = raw.strip()
    if " " in value:
        whole, frac = value.split(" ", 1)
        frac_value = _parse_fraction(frac.strip())
        if frac_value is None:
            return None
        return float(whole) + frac_value
    if "-" in value:
        whole, frac = value.split("-", 1)
        frac_value = _parse_fraction(frac.strip())
        if frac_value is None:
            return None
        return float(whole) + frac_value
    if "/" in value:
        return _parse_fraction(value)
    try:
        return float(value)
    except ValueError:
        return None


def _parse_fraction(raw: str) -> float | None:
    if "/" not in raw:
        return None
    numerator, denominator = raw.split("/", 1)
    try:
        return float(numerator) / float(denominator)
    except ValueError:
        return None


def _normalize_claim_value(claim: Claim) -> str:
    if claim.source_field in _NUMERIC_FIELDS or claim.source_field == "weight_capacity":
        numeric = _extract_numeric(claim.source_value)
        if numeric is not None:
            return _format_number(numeric)
    return _normalize_whitespace(claim.source_value.lower())


def _extract_numeric(text: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _format_number(value: float) -> str:
    formatted = f"{value:.3f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    for span_start, span_end in spans:
        if start < span_end and end > span_start:
            return True
    return False
