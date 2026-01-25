"""Deterministic keyword placement plan builder and validator."""
from __future__ import annotations

from dataclasses import dataclass
import re

from feedops.models import Candidate, ParentSKU
from feedops.pipeline.enrichment import Evidence
from feedops.pipeline import evidence as evidence_module


_WORD_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_BRAND = "Allied Brass"

_MATERIAL_PHRASES = [
    "solid brass",
    "stainless steel",
    "stainless",
    "steel",
    "brass",
    "glass",
    "wood",
    "zinc",
    "aluminum",
]

_FEATURE_GUARDS = [
    "ada",
    "ada compliant",
    "reeded",
    "l-shaped",
    "tilting",
    "pivot",
    "swing arm",
    "lighted",
    "magnifying",
    "recessed",
    "covered",
    "double",
    "train rack",
    "with shelf",
    "wall mount",
    "freestanding",
]

_CATEGORY_MAP: dict[str, dict[str, list[str] | str]] = {
    "Towel Bars": {
        "product_type_tokens": [
            "towel bar",
            "bath towel bar",
            "towel holder",
            "bath towel holder",
            "towel rack",
            "towel rail",
        ],
        "fallback_anchor": "towel bar",
        "fallback_description_terms": ["bath towel holder", "towel rack"],
    },
    "Grab Bars": {
        "product_type_tokens": ["grab bar", "bathroom grab bar", "safety grab bar"],
        "fallback_anchor": "grab bar",
        "fallback_description_terms": ["bathroom grab bar", "safety grab bar"],
    },
    "Toilet Paper Holders": {
        "product_type_tokens": ["toilet paper holder", "tissue holder", "toilet tissue holder"],
        "fallback_anchor": "toilet paper holder",
        "fallback_description_terms": ["tissue holder"],
    },
    "Towel Rings": {
        "product_type_tokens": ["towel ring", "hand towel ring"],
        "fallback_anchor": "towel ring",
        "fallback_description_terms": ["hand towel ring"],
    },
    "Robe Hooks": {
        "product_type_tokens": ["robe hook", "towel hook", "bathroom hook"],
        "fallback_anchor": "robe hook",
        "fallback_description_terms": ["towel hook"],
    },
    "Cabinet Knobs": {
        "product_type_tokens": ["cabinet knob", "drawer knob"],
        "fallback_anchor": "cabinet knob",
        "fallback_description_terms": ["drawer knob"],
    },
    "Glass Shelves": {
        "product_type_tokens": ["glass shelf", "bath shelf"],
        "fallback_anchor": "glass shelf",
        "fallback_description_terms": ["bath shelf"],
    },
    "Wall Mirrors": {
        "product_type_tokens": ["wall mirror", "bath mirror", "vanity mirror"],
        "fallback_anchor": "wall mirror",
        "fallback_description_terms": ["vanity mirror"],
    },
    "Make-Up Mirrors": {
        "product_type_tokens": ["make-up mirror", "makeup mirror", "vanity mirror"],
        "fallback_anchor": "make-up mirror",
        "fallback_description_terms": ["makeup mirror"],
    },
    "Soap Dishes": {
        "product_type_tokens": ["soap dish", "soap holder"],
        "fallback_anchor": "soap dish",
        "fallback_description_terms": ["soap holder"],
    },
}


@dataclass(frozen=True)
class KeywordPlacementPlan:
    """Structured placement guidance for intent keywords."""

    title_anchor: str
    short_title_anchor: str | None
    title_support_terms: list[str]
    description_terms: list[str]
    description_min_required: int
    description_first_150_required: int
    brand: str = _DEFAULT_BRAND


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


def _collect_keywords(evidence_rows: list[Evidence], field: str) -> list[str]:
    values: list[str] = []
    for row in evidence_rows:
        if row.field == field:
            values.extend(_split_keywords(row.value))
    return values


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = _normalize(term)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(term)
    return out


def _material_matches(term: str, material: str | None) -> bool:
    if not material:
        return True
    term_lower = term.lower()
    material_lower = material.lower()
    for phrase in _MATERIAL_PHRASES:
        if phrase in term_lower:
            required_tokens = phrase.split()
            return all(token in material_lower for token in required_tokens)
    return True


def _feature_supported(term: str, signal_text: str) -> bool:
    term_lower = term.lower()
    for guard in _FEATURE_GUARDS:
        if guard in term_lower and guard not in signal_text:
            return False
    return True


def _filter_terms(
    terms: list[str],
    *,
    parent_sku: ParentSKU,
    evidence_rows: list[Evidence],
) -> list[str]:
    finish_phrases, finish_tokens = evidence_module._build_finish_filters(parent_sku)
    signal_text = _build_feature_signal_text(parent_sku, evidence_rows)
    out: list[str] = []
    for term in terms:
        if evidence_module._is_finish_specific_keyword(term, finish_phrases, finish_tokens):
            continue
        if not _material_matches(term, parent_sku.material):
            continue
        if not _feature_supported(term, signal_text):
            continue
        out.append(term)
    return out


def _build_feature_signal_text(parent_sku: ParentSKU, evidence_rows: list[Evidence]) -> str:
    pieces = [
        parent_sku.current_title or "",
        parent_sku.current_description or "",
        parent_sku.mounting_type or "",
        parent_sku.category or "",
        parent_sku.style or "",
    ]
    for row in evidence_rows:
        if row.field == "feature_title_keywords":
            pieces.append(row.value)
    return " ".join(pieces).lower()


def _category_tokens(category: str) -> list[str]:
    config = _CATEGORY_MAP.get(category)
    if config:
        tokens = config.get("product_type_tokens", [])
        return [str(t) for t in tokens]
    return [_singularize(category)]


def _fallback_anchor(category: str) -> str:
    config = _CATEGORY_MAP.get(category)
    if config:
        anchor = config.get("fallback_anchor")
        if isinstance(anchor, str):
            return anchor
    return _singularize(category)


def _fallback_description_terms(category: str) -> list[str]:
    config = _CATEGORY_MAP.get(category)
    if config:
        terms = config.get("fallback_description_terms", [])
        return [str(t) for t in terms]
    return []


def _singularize(category: str) -> str:
    value = (category or "").strip().lower()
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value or "product"


def _select_anchor(terms: list[str], category_tokens: list[str]) -> str | None:
    for term in terms:
        term_lower = term.lower()
        if any(token in term_lower for token in category_tokens):
            return term
    return None


def _truncate_phrase(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    trimmed = text[:max_len].rstrip()
    if " " not in trimmed:
        return trimmed
    return trimmed.rsplit(" ", 1)[0]


def build_keyword_placement_plan(
    parent_sku: ParentSKU,
    evidence_rows: list[Evidence],
) -> KeywordPlacementPlan:
    """Build deterministic placement plan from evidence keywords."""
    intent_terms = _collect_keywords(evidence_rows, "keyword_intent_master")
    external_terms = _collect_keywords(evidence_rows, "external_keywords")
    design_terms = _collect_keywords(evidence_rows, "design_intent_keywords")
    feature_terms = _collect_keywords(evidence_rows, "feature_title_keywords")

    intent_terms = _filter_terms(intent_terms, parent_sku=parent_sku, evidence_rows=evidence_rows)
    external_terms = _filter_terms(external_terms, parent_sku=parent_sku, evidence_rows=evidence_rows)
    secondary_terms = _filter_terms(
        design_terms + feature_terms,
        parent_sku=parent_sku,
        evidence_rows=evidence_rows,
    )

    all_terms = _dedupe_terms(intent_terms + external_terms + secondary_terms)

    category_tokens = _category_tokens(parent_sku.category)
    anchor = _select_anchor(intent_terms, category_tokens)
    if not anchor:
        anchor = _select_anchor(external_terms, category_tokens)
    if not anchor:
        anchor = _fallback_anchor(parent_sku.category)

    title_support_terms = [
        term for term in _dedupe_terms(intent_terms + external_terms) if term != anchor
    ][:2]

    description_terms = [term for term in all_terms if term != anchor]
    if len(description_terms) < 2:
        description_terms.extend(_fallback_description_terms(parent_sku.category))
        description_terms = _dedupe_terms(description_terms)

    short_title_anchor = None
    if anchor:
        if len(anchor) <= 70:
            short_title_anchor = anchor
        else:
            short_title_anchor = _truncate_phrase(anchor, 70)

    return KeywordPlacementPlan(
        title_anchor=anchor,
        short_title_anchor=short_title_anchor,
        title_support_terms=title_support_terms,
        description_terms=description_terms[:6],
        description_min_required=2,
        description_first_150_required=1,
        brand=_DEFAULT_BRAND,
    )


def format_keyword_placement_section(plan: KeywordPlacementPlan) -> str:
    """Format placement guidance for prompt injection."""
    lines = [
        "## Keyword Placement Plan (Deterministic)",
        "",
        "These phrases represent search intent only; do NOT treat them as product facts or claims.",
        "",
        f"Title anchor (must appear verbatim in the first 70 characters): {plan.title_anchor}",
    ]
    if plan.short_title_anchor:
        lines.append(f"Google short title must include: {plan.short_title_anchor}")
    if plan.title_support_terms:
        lines.append("")
        lines.append("Title support terms (after 70 chars when space allows):")
        for term in plan.title_support_terms:
            lines.append(f"- {term}")
    if plan.description_terms:
        lines.append("")
        lines.append(
            "Description terms (include at least "
            f"{plan.description_min_required}; at least "
            f"{plan.description_first_150_required} in first 150 chars):"
        )
        for term in plan.description_terms:
            lines.append(f"- {term}")
    lines.append("")
    lines.append(f"Brand rule: titles must end with {plan.brand}")
    return "\n".join(lines)


def _strip_html(text: str) -> str:
    if "<" not in text:
        return text
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _contains_term(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def validate_candidate_keyword_placement(
    candidate: Candidate,
    plan: KeywordPlacementPlan,
) -> list[str]:
    """Validate candidate adheres to keyword placement plan."""
    errors: list[str] = []

    anchor = plan.title_anchor.strip()
    if anchor:
        for field in ("google_title", "bing_title", "shopify_title"):
            value = getattr(candidate, field, "")
            if not _contains_term(value[:70], anchor):
                errors.append(
                    f"{field} missing title anchor in first 70 chars: {plan.title_anchor}"
                )

    if plan.short_title_anchor:
        short_title = candidate.google_short_title or ""
        if not _contains_term(short_title, plan.short_title_anchor):
            errors.append(
                f"google_short_title missing title anchor: {plan.short_title_anchor}"
            )

    brand_lower = plan.brand.lower()
    for field in ("google_title", "bing_title", "shopify_title"):
        value = getattr(candidate, field, "")
        if not value.rstrip().lower().endswith(brand_lower):
            errors.append(f"{field} must end with {plan.brand}")

    if plan.description_terms:
        for field in ("google_description", "bing_description", "shopify_description"):
            raw = getattr(candidate, field, "")
            text = _strip_html(raw)
            lower_text = text.lower()
            matches = [
                term for term in plan.description_terms if term.lower() in lower_text
            ]
            if plan.description_first_150_required:
                opening = text[:150].lower()
                if not any(term.lower() in opening for term in plan.description_terms):
                    errors.append(
                        f"{field} missing description term in first 150 chars"
                    )
            if plan.description_min_required and len(matches) < plan.description_min_required:
                errors.append(
                    f"{field} missing {plan.description_min_required} description term(s); "
                    f"found {len(matches)}"
                )

    return errors
