"""Candidate selection utilities for multi-generation runs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from feedops.models import Candidate
from feedops.pipeline.keyword_placement import (
    KeywordPlacementPlan,
    get_canonical_product_type,
    validate_candidate_keyword_placement,
)
from feedops.pipeline.validators import (
    CUSTOMER_FIELDS,
    PARENTHETICAL_CITATION_PATTERN,
    validate_candidate_content,
)
from feedops.quality.scoring import CandidateHeuristicScore, score_candidate

DEFAULT_NUM_CANDIDATES = 3
DEFAULT_WEIGHTS = {"google": 0.7, "bing": 0.15, "shopify": 0.15}

# Title fields that need title case normalization
TITLE_FIELDS = {"google_title", "bing_title", "shopify_title", "google_short_title"}

# Acronyms to preserve in uppercase during title case conversion
_PRESERVE_UPPERCASE = {"ADA", "LED", "USA", "UK", "UV"}

# Product type synonyms for canonical enforcement and deduplication
_PRODUCT_TYPE_SYNONYMS = {
    "towel bar": ["towel holder", "towel rack", "towel rail", "bath bar"],
    "grab bar": ["safety bar", "support bar", "assist bar"],
    "cabinet knob": ["drawer knob", "cabinet pull", "drawer pull"],
    "toilet paper holder": ["tissue holder", "tp holder", "toilet roll holder"],
    "towel ring": ["towel loop", "hand towel holder"],
    "robe hook": ["coat hook", "towel hook"],
    "glass shelf": ["bath shelf", "bathroom shelf"],
    "wall mirror": ["bath mirror", "vanity mirror"],
    "makeup mirror": ["make-up mirror", "cosmetic mirror"],
    "soap dish": ["soap holder", "soap tray"],
}


# Patterns for SEO keyword spam to strip from descriptions
_KEYWORD_SPAM_PATTERNS = [
    r"Search terms shoppers use:[^\n]*\n?",
    r"Keywords:[^\n]*\n?",
    r"Related searches:[^\n]*\n?",
    r"Popular search terms:[^\n]*\n?",
]


def _strip_keyword_spam(text: str) -> str:
    """Remove SEO keyword lists from descriptions.

    These patterns sometimes appear when the LLM includes keyword research
    directly in customer-facing content instead of weaving keywords naturally.
    """
    result = text
    for pattern in _KEYWORD_SPAM_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result.strip()


def normalize_bullets(text: str) -> str:
    """Standardize bullet format: Unicode bullets to dash, remove empties.

    Applied to all description fields after LLM generation to fix:
    - Unicode bullet characters (``\\u2022``) replaced with ``- ``
    - Asterisk bullets replaced with ``- ``
    - Empty bullet lines removed
    """
    # Replace Unicode bullets and asterisk bullets with dash
    text = text.replace("\u2022 ", "- ").replace("\u2022", "- ")
    text = re.sub(r"^(\s*)\* ", r"\1- ", text, flags=re.MULTILINE)
    # Remove empty bullet lines (just "- " or "-" with nothing after)
    lines = text.split("\n")
    lines = [line for line in lines if line.strip() not in ("-", "- ", "- \r")]
    return "\n".join(lines)


def _ensure_brand_format(title: str) -> str:
    """Ensure Allied Brass is present once and is the last comma-separated segment."""
    # Remove any trailing brand first (various formats)
    brand_patterns = [
        r"\s*\|\s*Allied Brass\s*$",  # | Allied Brass
        r"\s*,\s*Allied Brass\s*$",  # , Allied Brass
        r"\s+Allied Brass\s*$",  # Allied Brass (no separator)
    ]
    clean_title = title
    for pattern in brand_patterns:
        clean_title = re.sub(pattern, "", clean_title)

    # Clean up any trailing separators or spaces
    clean_title = clean_title.rstrip(" ,|")

    # Re-add brand with comma separator
    if not clean_title:
        return "Allied Brass"
    return f"{clean_title}, Allied Brass"


def _smart_title_case(text: str) -> str:
    """Apply title case while preserving known acronyms and handling separators."""
    # Prefer commas, but tolerate pipes from legacy inputs.
    normalized = text.replace("|", ",")
    parts = normalized.split(",")
    result_parts = []
    for part in parts:
        words = part.strip().split()
        titled_words = []
        for word in words:
            # Preserve known acronyms
            if word.upper() in _PRESERVE_UPPERCASE:
                titled_words.append(word.upper())
            # Handle hyphenated words (e.g., "16-Inch")
            elif "-" in word:
                titled_words.append(
                    "-".join(
                        w.upper() if w.upper() in _PRESERVE_UPPERCASE else w.title()
                        for w in word.split("-")
                    )
                )
            else:
                titled_words.append(word.title())
        result_parts.append(" ".join(titled_words))
    return ", ".join([p for p in result_parts if p.strip()])


def _enforce_canonical_product_type(title: str, canonical: str | None) -> str:
    """Replace non-canonical product types with canonical form in title."""
    if not canonical:
        return title
    canonical_lower = canonical.lower()
    for canon, synonyms in _PRODUCT_TYPE_SYNONYMS.items():
        if canon == canonical_lower:
            for syn in synonyms:
                pattern = re.compile(re.escape(syn), re.IGNORECASE)
                title = pattern.sub(canonical, title)
            break
    return re.sub(r"\s+", " ", title).strip()


def _dedupe_product_types(title: str) -> str:
    """Remove redundant product type synonyms from title."""
    title_lower = title.lower()

    for canonical, synonyms in _PRODUCT_TYPE_SYNONYMS.items():
        if canonical in title_lower:
            for synonym in synonyms:
                if synonym in title_lower:
                    pattern = re.compile(re.escape(synonym), re.IGNORECASE)
                    title = pattern.sub("", title)

    return re.sub(r"\s+", " ", title).strip()


def _trim_google_short_title(title: str, max_len: int = 70) -> str:
    """Trim google_short_title to fit overlay constraints."""
    cleaned = title.strip()
    if len(cleaned) <= max_len:
        return cleaned

    brand_index = cleaned.lower().rfind("allied brass")
    if brand_index != -1:
        cleaned = cleaned[:brand_index].rstrip()
        cleaned = cleaned.rstrip(" |-—–")

    if len(cleaned) > max_len:
        for sep in [" | ", " - ", " — ", " – "]:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0].rstrip()
                break

    if len(cleaned) > max_len:
        truncated = cleaned[:max_len].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        cleaned = truncated.rstrip()

    return cleaned or title.strip()[:max_len]


@dataclass
class RankedCandidate:
    candidate: Candidate
    heuristic: CandidateHeuristicScore
    validation_errors: list[str]
    index: int
    keyword_errors: list[str] | None = None


def parse_num_candidates(env_value: str | None) -> int:
    """Parse candidate count from env/CLI."""
    if not env_value:
        return DEFAULT_NUM_CANDIDATES
    try:
        value = int(env_value)
    except (TypeError, ValueError):
        return DEFAULT_NUM_CANDIDATES
    return value if value > 0 else DEFAULT_NUM_CANDIDATES


def parse_candidate_weights(raw: str | None) -> dict[str, float]:
    """Parse weights from 'google=0.7,bing=0.15,shopify=0.15' string."""
    if not raw:
        return DEFAULT_WEIGHTS.copy()

    weights: dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if key not in DEFAULT_WEIGHTS:
            continue
        try:
            amount = float(value.strip())
        except ValueError:
            continue
        if amount > 1:
            amount = amount / 100
        if amount < 0:
            amount = 0
        weights[key] = amount

    total = sum(weights.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()

    return {k: v / total for k, v in weights.items()}


def sanitize_candidate_content(
    candidate: Candidate, category: str | None = None
) -> Candidate:
    """Strip catalog_csv citations, normalize title casing, and enforce canonical product types."""
    canonical = get_canonical_product_type(category) if category else None

    # Description fields that need keyword spam stripping
    description_fields = {
        "google_description",
        "bing_description",
        "shopify_description",
    }

    def _sanitize(value: str) -> str:
        cleaned = PARENTHETICAL_CITATION_PATTERN.sub("", value)
        cleaned = cleaned.replace("catalog_csv.", "")
        cleaned = re.sub(r" {2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    updates = {}
    for field in CUSTOMER_FIELDS:
        value = _sanitize(getattr(candidate, field))
        # Apply title case and brand formatting to title fields
        if field in TITLE_FIELDS:
            value = _smart_title_case(value)
            # Enforce canonical product type in titles
            if canonical:
                value = _enforce_canonical_product_type(value, canonical)
            # Ensure proper brand format with pipe separator
            if field != "google_short_title":
                value = _ensure_brand_format(value)
        # Dedupe and trim redundant product types in short title
        if field == "google_short_title":
            value = _dedupe_product_types(value)
            value = _trim_google_short_title(value)
        # Strip SEO keyword spam and normalize bullets in descriptions
        if field in description_fields:
            value = _strip_keyword_spam(value)
            value = normalize_bullets(value)
        updates[field] = value
    return candidate.model_copy(update=updates)


def rank_candidates(
    candidates: list[Candidate],
    weights: dict[str, float],
    keyword_plan: KeywordPlacementPlan | None = None,
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for idx, candidate in enumerate(candidates):
        if keyword_plan:
            heuristic = score_candidate(
                candidate, weights=weights, keyword_plan=keyword_plan
            )
        else:
            heuristic = score_candidate(candidate, weights=weights)
        validation_errors = validate_candidate_content(candidate)
        keyword_errors: list[str] = []
        if keyword_plan:
            keyword_errors = validate_candidate_keyword_placement(candidate, keyword_plan)
        candidate_index = (
            candidate.candidate_index if candidate.candidate_index is not None else idx
        )
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                heuristic=heuristic,
                validation_errors=validation_errors,
                index=candidate_index,
                keyword_errors=keyword_errors,
            )
        )
    return ranked


def _rank_sort_key(entry: RankedCandidate) -> tuple[bool, float, int, float, int]:
    return (
        bool(entry.validation_errors),           # Hard errors first
        -entry.heuristic.adjusted_weighted_composite,
        len(entry.keyword_errors or []),          # Fewer keyword misses preferred
        -entry.heuristic.google.composite,
        entry.index,
    )


def select_best_candidate(
    candidates: list[Candidate],
    weights: dict[str, float],
    keyword_plan: KeywordPlacementPlan | None = None,
    category: str | None = None,
) -> tuple[Candidate, list[RankedCandidate]]:
    """Select best candidate using validation-first + weighted heuristics."""
    if not candidates:
        raise ValueError("No candidates to select from")

    ranked = rank_candidates(candidates, weights, keyword_plan=keyword_plan)
    ranked_sorted = sorted(ranked, key=_rank_sort_key)
    best = ranked_sorted[0]
    selected = best.candidate

    # Always sanitize to apply canonical product types and deduplication
    sanitized = sanitize_candidate_content(selected, category=category)
    sanitized_errors = validate_candidate_content(sanitized)
    sanitized_keyword_errors: list[str] = []
    if keyword_plan:
        sanitized_keyword_errors = validate_candidate_keyword_placement(sanitized, keyword_plan)
    ranked_sorted[0] = RankedCandidate(
        candidate=sanitized,
        heuristic=best.heuristic,
        validation_errors=sanitized_errors,
        index=best.index,
        keyword_errors=sanitized_keyword_errors,
    )
    selected = sanitized

    return selected, ranked_sorted
