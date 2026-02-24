"""Deterministic keyword placement plan builder and validator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from feedops.models import Candidate, ParentSKU
from feedops.pipeline import evidence as evidence_module
from feedops.pipeline.enrichment import Evidence

_WORD_RE = re.compile(r"[a-z0-9]+")
_DEFAULT_BRAND = "Allied Brass"
_SEARCH_QUERY_PATTERN = re.compile(r'"([^"]+)"\s*\(([^)]*)\)')
_BING_SLASH_LIST_PATTERN = re.compile(r"\b[\w-]+(?:\s+[\w-]+)?\s*/\s*[\w-]+", re.IGNORECASE)
_BING_PARENTHETICAL_LIST_PATTERN = re.compile(r"\([^)]*(?:\bor\b|/)[^)]*\)", re.IGNORECASE)
_BING_DIMENSION_DUMP_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?\s*(?:in|inch(?:es)?|\")\s*[/,]\s*){2,}\d+(?:\.\d+)?\s*(?:in|inch(?:es)?|\")",
    re.IGNORECASE,
)
_STOP_WORDS = {"and", "or", "the", "a", "an", "with", "for", "in", "of", "on"}
_INTENT_NOISE_TOKENS = {
    "if",
    "you",
    "your",
    "search",
    "searching",
    "searched",
    "looking",
    "shop",
    "shopping",
    "compare",
    "comparing",
    "best",
    "buy",
    "online",
    "near",
    "me",
    "vs",
    "versus",
}

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
        "product_type_tokens": [
            "toilet paper holder",
            "tissue holder",
            "toilet tissue holder",
        ],
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
    "Paper Towel Holders": {
        "product_type_tokens": [
            "paper towel holder",
            "paper towel stand",
            "countertop paper towel holder",
        ],
        "fallback_anchor": "paper towel holder",
        "fallback_description_terms": [
            "paper towel stand",
            "kitchen paper towel holder",
        ],
    },
    "Tumbler Toothbrush Holders": {
        "product_type_tokens": [
            "tumbler holder",
            "toothbrush holder",
            "tumbler toothbrush holder",
        ],
        "fallback_anchor": "tumbler toothbrush holder",
        "fallback_description_terms": ["tumbler holder", "toothbrush holder"],
    },
    "Towel Shelves": {
        "product_type_tokens": ["towel shelf", "towel rack", "hotel towel shelf"],
        "fallback_anchor": "towel shelf",
        "fallback_description_terms": ["towel rack", "hotel towel rack"],
    },
    "Guest Towel Holders": {
        "product_type_tokens": [
            "guest towel holder",
            "guest towel tray",
            "towel holder",
        ],
        "fallback_anchor": "guest towel holder",
        "fallback_description_terms": ["guest towel tray"],
    },
    "Squeegee": {
        "product_type_tokens": ["shower squeegee", "squeegee"],
        "fallback_anchor": "shower squeegee",
        "fallback_description_terms": ["shower squeegee", "glass squeegee"],
    },
    "Multi Hooks": {
        "product_type_tokens": ["multi hook", "double hook", "robe hook"],
        "fallback_anchor": "multi hook",
        "fallback_description_terms": ["robe hook", "bathroom hook"],
    },
    "Freestanding Toilet Tissue Stands": {
        "product_type_tokens": [
            "toilet tissue stand",
            "toilet paper stand",
            "freestanding toilet paper holder",
        ],
        "fallback_anchor": "toilet paper stand",
        "fallback_description_terms": [
            "freestanding toilet paper holder",
            "toilet tissue stand",
        ],
    },
    "Shower Door Hardware": {
        "product_type_tokens": [
            "shower door handle",
            "shower door knob",
            "shower door hardware",
        ],
        "fallback_anchor": "shower door handle",
        "fallback_description_terms": ["shower door knob", "shower door hardware"],
    },
    "Shower Curtain Brackets and Rods": {
        "product_type_tokens": ["shower curtain rod", "shower rod", "curtain rod"],
        "fallback_anchor": "shower curtain rod",
        "fallback_description_terms": ["shower rod", "curtain rod"],
    },
    "Cabinet Hardware": {
        "product_type_tokens": [
            "cabinet pull",
            "cabinet knob",
            "drawer pull",
            "cabinet hardware",
        ],
        "fallback_anchor": "cabinet pull",
        "fallback_description_terms": ["drawer pull", "cabinet hardware"],
    },
    "Baskets": {
        "product_type_tokens": [
            "basket",
            "shower basket",
            "corner basket",
            "wire basket",
        ],
        "fallback_anchor": "shower basket",
        "fallback_description_terms": ["wire basket", "corner basket"],
    },
    "Assorted Wall Accessories": {
        "product_type_tokens": [],
        "fallback_anchor": None,
        "fallback_description_terms": ["bathroom accessories", "wall accessories"],
    },
    "Assorted Free Standing Accessories": {
        "product_type_tokens": [],
        "fallback_anchor": None,
        "fallback_description_terms": [
            "bathroom accessories",
            "freestanding accessories",
        ],
    },
    "Retractable Hooks and Garment Rods": {
        "product_type_tokens": ["retractable hook", "garment rod", "wall hook"],
        "fallback_anchor": None,
        "fallback_description_terms": ["retractable hook", "garment rod", "wall hook"],
    },
}

# Canonical product type names for consistent title terminology
_CANONICAL_PRODUCT_TYPES = {
    "Towel Bars": "Towel Bar",
    "Grab Bars": "Grab Bar",
    "Cabinet Knobs": "Cabinet Knob",
    "Toilet Paper Holders": "Toilet Paper Holder",
    "Towel Rings": "Towel Ring",
    "Robe Hooks": "Robe Hook",
    "Glass Shelves": "Glass Shelf",
    "Wall Mirrors": "Wall Mirror",
    "Make-Up Mirrors": "Makeup Mirror",
    "Soap Dishes": "Soap Dish",
    "Paper Towel Holders": "Paper Towel Holder",
    "Tumbler Toothbrush Holders": "Tumbler Toothbrush Holder",
    "Towel Shelves": "Towel Shelf",
    "Guest Towel Holders": "Guest Towel Holder",
    "Squeegee": "Squeegee",
    "Multi Hooks": "Multi Hook",
    "Freestanding Toilet Tissue Stands": "Toilet Paper Stand",
    "Shower Door Hardware": "Shower Door Handle",
    "Shower Curtain Brackets and Rods": "Shower Curtain Rod",
    "Cabinet Hardware": "Cabinet Pull",
    "Baskets": "Basket",
}


def get_canonical_product_type(category: str) -> str | None:
    """Return the canonical product type for a category."""
    return _CANONICAL_PRODUCT_TYPES.get(category)


# Room context mapping for kitchen vs bathroom language
_CATEGORY_ROOM_CONTEXT = {
    # Kitchen categories
    "Paper Towel Holders": "kitchen",
    "Kitchen Towel Bars": "kitchen",
    "Kitchen Accessories": "kitchen",
    # Bathroom categories
    "Towel Bars": "bathroom",
    "Grab Bars": "bathroom",
    "Toilet Paper Holders": "bathroom",
    "Towel Rings": "bathroom",
    "Robe Hooks": "bathroom",
    "Glass Shelves": "bathroom",
    "Wall Mirrors": "bathroom",
    "Make-Up Mirrors": "bathroom",
    "Soap Dishes": "bathroom",
    "Tumbler Toothbrush Holders": "bathroom",
    "Towel Shelves": "bathroom",
    "Guest Towel Holders": "bathroom",
    "Squeegee": "bathroom",
    "Multi Hooks": "bathroom",
    "Freestanding Toilet Tissue Stands": "bathroom",
    "Shower Door Hardware": "bathroom",
    "Shower Curtain Brackets and Rods": "bathroom",
    "Baskets": "bathroom",
    "Assorted Wall Accessories": "bathroom",
    "Assorted Free Standing Accessories": "bathroom",
    "Retractable Hooks and Garment Rods": "bathroom",
    # Not room-specific
    "Cabinet Knobs": None,
    "Cabinet Hardware": None,
}


def get_room_context(category: str) -> str | None:
    """Return room context for a category (kitchen, bathroom, or None)."""
    return _CATEGORY_ROOM_CONTEXT.get(category, "bathroom")


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
    room_context: str | None = None
    enforce_alignment: bool = False
    distilled_intent_terms: list[str] = field(default_factory=list)
    buyer_phrasing_hints: list[str] = field(default_factory=list)


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


def _distill_intent_term(term: str) -> str | None:
    """Collapse raw query fragments into clean buyer-intent phrases."""
    tokens = _WORD_RE.findall((term or "").lower())
    if not tokens:
        return None

    cleaned: list[str] = []
    for token in tokens:
        if token in _INTENT_NOISE_TOKENS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        cleaned.append(token)

    if not cleaned:
        return None

    phrase = " ".join(cleaned[:6]).strip()
    if len(phrase) < 4:
        return None
    return phrase


def _distill_intent_terms(terms: list[str], *, top_n: int = 6) -> list[str]:
    distilled: list[str] = []
    seen: set[str] = set()
    for term in terms:
        phrase = _distill_intent_term(term)
        if not phrase:
            continue
        key = _normalize(phrase)
        if not key or key in seen:
            continue
        seen.add(key)
        distilled.append(phrase)
        if len(distilled) >= top_n:
            break
    return distilled


def _parse_metric_score(metric: str) -> float:
    """Parse volume/impression text (e.g. '2.4K vol') into sortable score."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", metric or "")
    if not match:
        return 0.0
    value = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix == "k":
        value *= 1000
    elif suffix == "m":
        value *= 1_000_000
    return value


def _collect_search_query_terms(evidence_rows: list[Evidence]) -> list[str]:
    """Extract ranked search query terms from evidence rows."""
    scored_terms: list[tuple[str, float]] = []
    for row in evidence_rows:
        if row.field not in {"search_queries_top", "variant_top_queries"}:
            continue
        for phrase, metric in _SEARCH_QUERY_PATTERN.findall(row.value or ""):
            term = phrase.strip()
            if not term:
                continue
            scored_terms.append((term, _parse_metric_score(metric)))

    if not scored_terms:
        return []

    scored_terms.sort(key=lambda entry: entry[1], reverse=True)
    ordered_terms = [term for term, _ in scored_terms]
    return _dedupe_terms(ordered_terms)


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
        if evidence_module._is_finish_specific_keyword(
            term, finish_phrases, finish_tokens
        ):
            continue
        if not _material_matches(term, parent_sku.material):
            continue
        if not _feature_supported(term, signal_text):
            continue
        out.append(term)
    return out


def _build_feature_signal_text(
    parent_sku: ParentSKU, evidence_rows: list[Evidence]
) -> str:
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


def _fallback_anchor(category: str, current_title: str | None = None) -> str:
    """Return a fallback title anchor for a category.

    Prefers a mapped anchor from ``_CATEGORY_MAP``.  When the map entry
    has ``fallback_anchor=None`` (e.g. broad categories like "Assorted
    Wall Accessories" or "Retractable Hooks and Garment Rods"), we fall
    back to the ``current_title`` because the category name doesn't
    describe a single product type.  As a last resort, singularize the
    category name.
    """
    config = _CATEGORY_MAP.get(category)
    if config:
        anchor = config.get("fallback_anchor")
        if isinstance(anchor, str):
            return anchor
        # fallback_anchor is None → category is too broad.
        # Use current_title if available.
        if current_title:
            return current_title.strip().lower()
    # Category not in map at all: try current_title, else singularize.
    if current_title:
        return current_title.strip().lower()
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
    search_query_terms = _collect_search_query_terms(evidence_rows)
    intent_terms = _collect_keywords(evidence_rows, "keyword_intent_master")
    external_terms = _collect_keywords(evidence_rows, "external_keywords")
    design_terms = _collect_keywords(evidence_rows, "design_intent_keywords")
    feature_terms = _collect_keywords(evidence_rows, "feature_title_keywords")

    search_query_terms = _filter_terms(
        search_query_terms, parent_sku=parent_sku, evidence_rows=evidence_rows
    )
    intent_terms = _filter_terms(
        intent_terms, parent_sku=parent_sku, evidence_rows=evidence_rows
    )
    external_terms = _filter_terms(
        external_terms, parent_sku=parent_sku, evidence_rows=evidence_rows
    )
    secondary_terms = _filter_terms(
        design_terms + feature_terms,
        parent_sku=parent_sku,
        evidence_rows=evidence_rows,
    )

    all_terms = _dedupe_terms(
        search_query_terms + intent_terms + external_terms + secondary_terms
    )
    distilled_terms = _distill_intent_terms(all_terms, top_n=6)

    category_tokens = _category_tokens(parent_sku.category)
    anchor_source = "fallback"
    anchor = _select_anchor(distilled_terms, category_tokens)
    if anchor:
        anchor_source = "distilled_intent_terms"
    if not anchor:
        anchor = _select_anchor(search_query_terms, category_tokens)
        if anchor:
            anchor_source = "search_queries_top"
    if not anchor:
        anchor = _select_anchor(intent_terms, category_tokens)
        if anchor:
            anchor_source = "keyword_intent_master"
    if not anchor:
        anchor = _select_anchor(external_terms, category_tokens)
        if anchor:
            anchor_source = "external_keywords"
    if not anchor:
        anchor = _fallback_anchor(parent_sku.category, parent_sku.current_title)
    distilled_anchor = _distill_intent_term(anchor)
    if distilled_anchor:
        anchor = distilled_anchor

    title_support_terms = [
        term
        for term in _distill_intent_terms(
            _dedupe_terms(search_query_terms + intent_terms + external_terms),
            top_n=6,
        )
        if term != anchor
    ][:2]

    description_terms = [
        term
        for term in _distill_intent_terms(
            _dedupe_terms(search_query_terms + all_terms),
            top_n=6,
        )
        if term != anchor
    ]
    if len(description_terms) < 2:
        description_terms.extend(
            _distill_intent_terms(
                _fallback_description_terms(parent_sku.category),
                top_n=6,
            )
        )
        description_terms = _dedupe_terms(description_terms)

    short_title_anchor = None
    if anchor:
        if len(anchor) <= 70:
            short_title_anchor = anchor
        else:
            short_title_anchor = _truncate_phrase(anchor, 70)

    buyer_hints = [term for term in description_terms if term != anchor][:4]

    return KeywordPlacementPlan(
        title_anchor=anchor,
        short_title_anchor=short_title_anchor,
        title_support_terms=title_support_terms,
        description_terms=description_terms[:6],
        description_min_required=2,
        description_first_150_required=0,  # Disabled: let model place keywords naturally
        brand=_DEFAULT_BRAND,
        room_context=get_room_context(parent_sku.category),
        enforce_alignment=anchor_source != "fallback",
        distilled_intent_terms=distilled_terms,
        buyer_phrasing_hints=buyer_hints,
    )


def format_keyword_placement_section(plan: KeywordPlacementPlan) -> str:
    """Format placement guidance for prompt injection."""
    lines = [
        "## Keyword Placement Plan (Deterministic)",
        "",
        "These phrases represent search intent only; do NOT treat them as product facts or claims.",
        "",
        f"Primary intent anchor (use naturally in the title; adapt wording to accurately describe THIS product): {plan.title_anchor}",
    ]
    if plan.distilled_intent_terms:
        lines.append("")
        lines.append("Distilled high-signal intent terms (top 6):")
        for term in plan.distilled_intent_terms:
            lines.append(f"- {term}")
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
            f"{plan.description_min_required} naturally in the description):"
        )
        for term in plan.description_terms:
            lines.append(f"- {term}")
    if plan.buyer_phrasing_hints:
        lines.append("")
        lines.append("Optional buyer phrasing hints (use only if natural):")
        for hint in plan.buyer_phrasing_hints:
            lines.append(f"- {hint}")
    lines.append("")
    lines.append(
        f"Brand rule: google_title and bing_title must end with {plan.brand}"
    )
    lines.append(
        f"Shopify rule: shopify_title must not include {plan.brand}"
    )
    if plan.room_context:
        lines.append("")
        lines.append(
            f"Room context: {plan.room_context} (use appropriate language; never describe as the other room type)"
        )
    return "\n".join(lines)


def _strip_html(text: str) -> str:
    if "<" not in text:
        return text
    cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _contains_term(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def _anchor_overlap(text: str, anchor: str, threshold: float = 0.6) -> bool:
    """Check if enough anchor tokens appear in text (token overlap, not exact match).

    Returns True if at least ``threshold`` fraction of the anchor's
    meaningful tokens appear in the text.  This allows the model to
    adapt "retractable hooks and garment rod" → "retractable wall hook"
    while still getting credit for including the core product type.
    """
    stop_words = {"and", "or", "the", "a", "an", "with", "for", "in", "of", "on"}
    anchor_tokens = [t for t in _WORD_RE.findall(anchor.lower()) if t not in stop_words]
    if not anchor_tokens:
        return True
    text_lower = text.lower()
    hits = sum(1 for t in anchor_tokens if t in text_lower)
    return hits / len(anchor_tokens) >= threshold


def validate_candidate_keyword_placement(
    candidate: Candidate,
    plan: KeywordPlacementPlan,
) -> list[str]:
    """Validate candidate adheres to keyword placement plan."""

    errors: list[str] = []

    anchor = plan.title_anchor.strip()
    if anchor:
        anchor_tokens = [
            t
            for t in _WORD_RE.findall(anchor.lower())
            if t not in {"and", "or", "the", "a", "an", "with", "for", "in", "of", "on"}
        ]
        for field in ("google_title", "bing_title", "shopify_title"):
            value = getattr(candidate, field, "")
            # Use token overlap: the model may adapt the anchor to better
            # describe the specific product (e.g. "retractable wall hook"
            # instead of "retractable hooks and garment rod").
            if not _anchor_overlap(value[:70], anchor):
                errors.append(
                    f"{field} missing title anchor in first 70 chars: {plan.title_anchor}"
                )

    if plan.short_title_anchor:
        short_title = candidate.google_short_title or ""
        if not _anchor_overlap(short_title, plan.short_title_anchor):
            errors.append(
                f"google_short_title missing title anchor: {plan.short_title_anchor}"
            )

    brand_lower = plan.brand.lower()
    for field in ("google_title", "bing_title"):
        value = getattr(candidate, field, "")
        if not value.rstrip().lower().endswith(brand_lower):
            errors.append(f"{field} must end with {plan.brand}")
    shopify_title = candidate.shopify_title or ""
    if brand_lower in shopify_title.lower():
        errors.append(f"shopify_title must not include {plan.brand}")

    if plan.description_terms:
        for field in ("google_description", "bing_description", "shopify_description"):
            raw = getattr(candidate, field, "")
            text = _strip_html(raw)
            lower_text = text.lower()
            # Token overlap: a term "matches" if its key tokens appear in the text,
            # not just as an exact substring (allows natural keyword integration).
            matches = [
                term
                for term in plan.description_terms
                if term.lower() in lower_text or _anchor_overlap(lower_text, term)
            ]
            if plan.description_first_150_required:
                # 150-char window aligns with snippet visibility requirements.
                opening = text[:150].lower()
                if not any(
                    term.lower() in opening or _anchor_overlap(opening, term)
                    for term in plan.description_terms
                ):
                    errors.append(
                        f"{field} missing description term in first 150 chars"
                    )
            if (
                plan.description_min_required
                and len(matches) < plan.description_min_required
            ):
                errors.append(
                    f"{field} missing {plan.description_min_required} description term(s); "
                    f"found {len(matches)}"
                )

    bing_text = _strip_html(candidate.bing_description or "")
    if _BING_SLASH_LIST_PATTERN.search(bing_text):
        errors.append(
            "bing_description contains slash-separated keyword list (anti-stuffing violation)"
        )
    if _BING_PARENTHETICAL_LIST_PATTERN.search(bing_text):
        errors.append(
            "bing_description contains parenthetical keyword list (anti-stuffing violation)"
        )
    if _BING_DIMENSION_DUMP_PATTERN.search(bing_text):
        errors.append(
            "bing_description contains dimension dump list (anti-stuffing violation)"
        )

    return errors
