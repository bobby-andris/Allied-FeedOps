"""Validation utilities for generated candidates.

Validates customer-facing content against Google Merchant Center policies,
Bing Shopping requirements, and general e-commerce best practices.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from feedops.models import Candidate

# Customer-facing fields that require validation
CUSTOMER_FIELDS = (
    "google_title",
    "google_short_title",
    "google_description",
    "bing_title",
    "bing_description",
    "shopify_title",
    "shopify_description",
)

# Title fields have stricter character limits
TITLE_FIELDS = (
    "google_title",
    "google_short_title",
    "bing_title",
    "shopify_title",
)

DESCRIPTION_FIELDS = (
    "google_description",
    "bing_description",
    "shopify_description",
)

# Character limits by platform (per Google/Bing/Shopify specs)
CHAR_LIMITS = {
    "google_title": 150,
    "google_short_title": 70,
    "google_description": 5000,
    "bing_title": 150,
    "bing_description": 10000,
    "shopify_title": 255,
    "shopify_description": None,  # No hard limit for Shopify HTML
}


# =============================================================================
# Validation Patterns
# =============================================================================

# Citation leakage patterns
PARENTHETICAL_CITATION_PATTERN = re.compile(r"\(catalog_csv\.[^)]+\)")
CITATION_PATTERN = re.compile(r"catalog_csv\.", re.IGNORECASE)

# ALL CAPS words (4+ consecutive uppercase letters, excluding common abbreviations)
ALL_CAPS_PATTERN = re.compile(r"\b[A-Z]{4,}\b")
# Allowed ALL CAPS abbreviations
ALLOWED_ALL_CAPS = {"HTML", "URL", "USA", "ADA", "GTIN", "UPC", "SKU", "ISBN"}

# URL detection
URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)

# Promotional language (prohibited in Google Merchant Center)
PROMOTIONAL_PATTERNS = [
    re.compile(r"\bfree\s+shipping\b", re.IGNORECASE),
    re.compile(r"\bsale\b", re.IGNORECASE),
    re.compile(r"\bdiscount(ed)?\b", re.IGNORECASE),
    re.compile(r"\bbest\s+price\b", re.IGNORECASE),
    re.compile(r"\blowest\s+price\b", re.IGNORECASE),
    re.compile(r"\bcheap(est)?\b", re.IGNORECASE),
    re.compile(r"\bbargain\b", re.IGNORECASE),
    re.compile(r"\blimited\s+time\b", re.IGNORECASE),
    re.compile(r"\bact\s+now\b", re.IGNORECASE),
    re.compile(r"\bbuy\s+now\b", re.IGNORECASE),
    re.compile(r"\border\s+now\b", re.IGNORECASE),
    re.compile(r"\bspecial\s+offer\b", re.IGNORECASE),
    re.compile(r"\bwhile\s+supplies\s+last\b", re.IGNORECASE),
    re.compile(r"\$\d+\s+off\b", re.IGNORECASE),
    re.compile(r"\b\d+%\s+off\b", re.IGNORECASE),
]

# SKU/ID leakage patterns (internal identifiers that shouldn't appear in content)
SKU_PATTERNS = [
    re.compile(r"\bshopify_\w+", re.IGNORECASE),
    re.compile(r"\bgmc_\w+", re.IGNORECASE),
    re.compile(r"\bsku[_-]?\d+", re.IGNORECASE),
    re.compile(r"\bitem[_-]?id[_-]?\d+", re.IGNORECASE),
    re.compile(r"\bproduct[_-]?id[_-]?\d+", re.IGNORECASE),
    re.compile(r"\boffer[_-]?id[_-]?\w+", re.IGNORECASE),
    # Shopify product/variant ID format
    re.compile(r"\b\d{13,}\b"),  # 13+ digit numbers (Shopify IDs)
]

# Excessive punctuation
EXCESSIVE_EXCLAMATION = re.compile(r"!{2,}")
EXCESSIVE_PUNCTUATION = re.compile(r"[!?]{3,}")

# Speculative competitive language (requires evidence and often triggers policy/safety issues)
SPECULATIVE_COMPETITIVE_PATTERNS = [
    re.compile(r"\bnot found in competitors?\b", re.IGNORECASE),
    re.compile(r"\bset(?:s)? this apart from competitors?\b", re.IGNORECASE),
    re.compile(r"\bbetter than\b", re.IGNORECASE),
    re.compile(r"\boutperform(?:s|ing)? competitors?\b", re.IGNORECASE),
    re.compile(r"\bbeat(?:s)? (?:the )?(?:competition|competitors?)\b", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    """Result of content validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]


def _check_all_caps(value: str, field: str) -> list[str]:
    """Check for ALL CAPS words that violate style guidelines."""
    errors = []
    matches = ALL_CAPS_PATTERN.findall(value)
    for match in matches:
        if match not in ALLOWED_ALL_CAPS:
            errors.append(f"{field} contains ALL CAPS word: {match}")
    return errors


def _check_urls(value: str, field: str) -> list[str]:
    """Check for URLs in content (prohibited in descriptions)."""
    errors = []
    if URL_PATTERN.search(value):
        errors.append(f"{field} contains URL (prohibited in product content)")
    return errors


def _check_promotional_language(value: str, field: str) -> list[str]:
    """Check for promotional language prohibited by Google Merchant Center."""
    errors = []
    for pattern in PROMOTIONAL_PATTERNS:
        match = pattern.search(value)
        if match:
            errors.append(
                f"{field} contains promotional language: '{match.group(0)}' "
                "(prohibited by Google Merchant Center)"
            )
    return errors


def _check_sku_leakage(value: str, field: str) -> list[str]:
    """Check for internal SKU/ID leakage in customer-facing content."""
    errors = []
    for pattern in SKU_PATTERNS:
        match = pattern.search(value)
        if match:
            errors.append(
                f"{field} contains internal identifier: '{match.group(0)}' "
                "(should not appear in customer-facing content)"
            )
    return errors


def _check_character_limits(value: str, field: str) -> list[str]:
    """Check character limits for platform compliance."""
    errors = []
    limit = CHAR_LIMITS.get(field)
    if limit is not None and len(value) > limit:
        errors.append(
            f"{field} exceeds character limit: {len(value)} > {limit} characters"
        )
    return errors


def _check_citation_leakage(value: str, field: str) -> list[str]:
    """Check for source citation leakage in customer-facing content."""
    errors = []
    parenthetical_match = PARENTHETICAL_CITATION_PATTERN.search(value)
    if parenthetical_match:
        errors.append(
            f"{field} contains parenthetical source reference {parenthetical_match.group(0)}"
        )
    elif CITATION_PATTERN.search(value):
        errors.append(f"{field} contains source citation reference 'catalog_csv.'")
    return errors


def _check_excessive_punctuation(value: str, field: str) -> list[str]:
    """Check for excessive punctuation that looks unprofessional."""
    warnings = []
    if EXCESSIVE_EXCLAMATION.search(value):
        warnings.append(f"{field} contains excessive exclamation marks")
    if EXCESSIVE_PUNCTUATION.search(value):
        warnings.append(f"{field} contains excessive punctuation")
    return warnings


def _check_speculative_competitive_claims(value: str, field: str) -> list[str]:
    """Check for broad competitive claims that are unsafe without direct evidence."""
    errors = []
    for pattern in SPECULATIVE_COMPETITIVE_PATTERNS:
        match = pattern.search(value)
        if match:
            errors.append(
                f"{field} contains speculative competitive claim: '{match.group(0)}' "
                "(use evidence-backed product facts instead)"
            )
    return errors


def validate_candidate_content(candidate: Candidate) -> list[str]:
    """Validate customer-facing fields for policy compliance.

    Checks for:
    - Citation/source reference leakage
    - ALL CAPS words (except allowed abbreviations)
    - URLs in content
    - Promotional language (prohibited by Google Merchant Center)
    - Internal SKU/ID leakage
    - Character limit violations

    Args:
        candidate: The candidate to validate

    Returns:
        List of error messages (empty if all validations pass)
    """
    errors: list[str] = []

    for field in CUSTOMER_FIELDS:
        value = getattr(candidate, field, "")
        if not value:
            continue

        # Critical validations (errors)
        errors.extend(_check_citation_leakage(value, field))
        errors.extend(_check_all_caps(value, field))
        errors.extend(_check_urls(value, field))
        errors.extend(_check_promotional_language(value, field))
        errors.extend(_check_sku_leakage(value, field))
        errors.extend(_check_character_limits(value, field))
        errors.extend(_check_speculative_competitive_claims(value, field))

    return errors


def validate_candidate_content_full(candidate: Candidate) -> ValidationResult:
    """Full validation with errors and warnings.

    Returns both hard errors (policy violations) and soft warnings
    (style issues that don't block publishing).

    Args:
        candidate: The candidate to validate

    Returns:
        ValidationResult with valid flag, errors, and warnings
    """
    errors: list[str] = []
    warnings: list[str] = []

    for field in CUSTOMER_FIELDS:
        value = getattr(candidate, field, "")
        if not value:
            continue

        # Critical validations (errors)
        errors.extend(_check_citation_leakage(value, field))
        errors.extend(_check_all_caps(value, field))
        errors.extend(_check_urls(value, field))
        errors.extend(_check_promotional_language(value, field))
        errors.extend(_check_sku_leakage(value, field))
        errors.extend(_check_character_limits(value, field))
        errors.extend(_check_speculative_competitive_claims(value, field))

        # Soft validations (warnings)
        warnings.extend(_check_excessive_punctuation(value, field))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def validate_title_structure(title: str, field: str = "title") -> list[str]:
    """Validate title structure for optimal search performance.

    Checks that titles follow Google Shopping best practices:
    - Product type should appear in first 30 characters (mobile visibility)
    - Key attributes should be in first 70 characters (desktop visibility)
    - Brand should be at the end

    Args:
        title: The title to validate
        field: Field name for error messages

    Returns:
        List of structural warnings
    """
    warnings = []

    # Check title length
    if len(title) < 30:
        warnings.append(
            f"{field} is very short ({len(title)} chars) - may miss search coverage"
        )

    # Check if brand is at end (Allied Brass should be last)
    lower_title = title.lower()
    if "allied brass" in lower_title:
        brand_pos = lower_title.rfind("allied brass")
        if brand_pos < len(title) - 20:  # Not in last 20 chars
            warnings.append(
                f"{field} has brand 'Allied Brass' not at end - "
                "brand should be the last segment for lesser-known brands"
            )

    # Check for a readable segment separator (recommended structure)
    # Accept pipes for backwards compatibility, but prefer commas/hyphens in generated titles.
    if " | " not in title and " - " not in title and "," not in title:
        warnings.append(
            f"{field} missing segment separator (comma, hyphen, or pipe) - "
            "consider separating major segments for readability"
        )

    return warnings


def validate_description_structure(
    description: str,
    field: str = "description",
    is_html: bool = False,
) -> list[str]:
    """Validate description structure for conversion optimization.

    Args:
        description: The description to validate
        field: Field name for error messages
        is_html: Whether the description is HTML (Shopify)

    Returns:
        List of structural warnings
    """
    warnings = []

    # Strip HTML for length calculation if needed
    text = description
    if is_html:
        text = re.sub(r"<[^>]+>", " ", description)
        text = re.sub(r"\s+", " ", text).strip()

    # Check minimum length
    if len(text) < 300:
        warnings.append(
            f"{field} is short ({len(text)} chars) - "
            "descriptions under 300 chars may lack detail for conversions"
        )
    elif len(text) < 500:
        warnings.append(
            f"{field} is moderate ({len(text)} chars) - "
            "500+ characters recommended for optimal conversion"
        )

    # Check for bullet structure
    has_bullets = bool(
        re.search(r"^[\s]*[-•]", description, re.MULTILINE)
        or (is_html and "<li" in description.lower())
    )
    if not has_bullets:
        warnings.append(
            f"{field} missing bullet points - "
            "structured highlights improve scannability"
        )

    # Check opening hook (first 150 chars should engage)
    opening = text[:150].lower()
    engagement_cues = [
        "upgrade",
        "protect",
        "transform",
        "create",
        "enjoy",
        "need",
        "tired of",
        "looking for",
        "never",
        "imagine",
    ]
    if not any(cue in opening for cue in engagement_cues):
        warnings.append(
            f"{field} opening may lack engagement hook - "
            "consider leading with benefit/problem"
        )

    return warnings


_FINISH_METADATA_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "finish-metadata.json"
)


@lru_cache(maxsize=1)
def _load_finish_names() -> tuple[str, ...]:
    """Load canonical finish names from finish-metadata.json.

    Used for lightweight validation (e.g., ensuring finish is visible early in
    variant titles when finish is the primary differentiator).
    """
    try:
        payload = json.loads(_FINISH_METADATA_PATH.read_text())
    except FileNotFoundError:
        return ()
    except json.JSONDecodeError:
        return ()

    finishes = payload.get("finishes", {})
    if not isinstance(finishes, dict):
        return ()
    return tuple(finishes.keys())


def _normalize_title_for_compare(title: str) -> str:
    title = (title or "").strip().casefold()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*\|\s*", " | ", title)
    title = re.sub(r"\s*,\s*", ", ", title)
    return title.strip(" ,|")


def _find_first_finish(title: str, finish_names: tuple[str, ...]) -> tuple[str, int] | None:
    if not title:
        return None

    # Prefer longer finish names first to avoid partial matches.
    for finish in sorted(finish_names, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(finish)}(?!\w)", re.IGNORECASE)
        match = pattern.search(title)
        if match:
            return (finish, match.start())
    return None


def validate_variant_title_uniqueness(
    titles: list[str],
    *,
    visible_chars: int = 70,
) -> list[str]:
    """Validate variant title differentiation to reduce cannibalization risk.

    This is a guardrail. It does NOT attempt to force variants to be "different";
    it flags two failure modes that hurt performance and trust:
      1) Exact duplicate titles across variants.
      2) Finish only appears after the first `visible_chars` characters, making
         variants look identical in common UI truncation zones.
    """
    warnings: list[str] = []
    if not titles:
        return warnings

    normalized = [_normalize_title_for_compare(t) for t in titles]
    counts: dict[str, int] = {}
    for key in normalized:
        counts[key] = counts.get(key, 0) + 1

    dupes = [k for k, c in counts.items() if k and c > 1]
    for dup in dupes:
        warnings.append(f"Duplicate variant title detected: '{dup}'")

    finish_names = _load_finish_names()
    if finish_names:
        for raw_title in titles:
            found = _find_first_finish(raw_title, finish_names)
            if not found:
                continue
            finish, pos = found
            if pos >= visible_chars:
                warnings.append(
                    f"Finish '{finish}' appears after the first {visible_chars} characters; "
                    "consider moving finish earlier for variant differentiation."
                )
                break

    return warnings
