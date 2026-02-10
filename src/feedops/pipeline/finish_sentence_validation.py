"""Validation helpers for variant finish sentences.

Phase 3 requirement:
- keep canonical finish keys only
- reject generic/keyword-dump boilerplate
- reject unsupported unverifiable claims
- keep sentences anchored to the specific product context
"""

from __future__ import annotations

import re
from typing import Iterable


_PRODUCT_ANCHOR_TERMS = {
    "towel",
    "bar",
    "rack",
    "holder",
    "hook",
    "shelf",
    "mirror",
    "grab",
    "basket",
    "caddy",
    "dispenser",
    "ring",
    "rod",
    "toilet",
    "paper",
    "soap",
    "shower",
    "vanity",
    "bathroom",
    "kitchen",
}

_BANNED_MARKETING_WORDS = re.compile(
    r"\b(finest|luxurious|premium|exclusive|exceptional|unparalleled|superior|exquisite|ultimate)\b",
    re.IGNORECASE,
)

_GENERIC_BOILERPLATE_PATTERNS = [
    re.compile(r"\bcomplements\s+any\s+decor\b", re.IGNORECASE),
    re.compile(r"\bperfect\s+for\s+any\s+bathroom\b", re.IGNORECASE),
    re.compile(r"\badds\s+(timeless|classic|elegant)\s+(style|elegance|charm)\b", re.IGNORECASE),
    re.compile(r"\bbrings\s+(timeless|classic|elegant)\s+(style|elegance|charm)\b", re.IGNORECASE),
]

_UNVERIFIABLE_PATTERNS = [
    re.compile(r"\bwaterproof\b", re.IGNORECASE),
    re.compile(r"\brustproof\b", re.IGNORECASE),
    re.compile(r"\bscratch[- ]proof\b", re.IGNORECASE),
    re.compile(r"\btarnish[- ]proof\b", re.IGNORECASE),
    re.compile(r"\bguaranteed?\b", re.IGNORECASE),
    re.compile(r"\bwill\s+never\b", re.IGNORECASE),
]


def _extract_anchor_terms(text: str) -> set[str]:
    text_lower = text.lower()
    return {term for term in _PRODUCT_ANCHOR_TERMS if term in text_lower}


def _contains_keyword_dump(sentence: str) -> bool:
    # Slash and parenthetical lists are the main anti-stuffing failures observed.
    if "/" in sentence:
        return True
    return bool(re.search(r"\([^)]*,[^)]*\)", sentence))


def validate_finish_sentence(
    *,
    finish_name: str,
    sentence: str,
    base_description: str,
) -> list[str]:
    """Validate one finish sentence and return violation messages."""
    violations: list[str] = []
    normalized = sentence.strip()
    if not normalized:
        return ["empty sentence"]

    if len(normalized) < 20:
        violations.append("too short (<20 chars)")
    if len(normalized) > 260:
        violations.append("too long (>260 chars)")

    if finish_name.lower() not in normalized.lower():
        violations.append("missing finish name")

    if _contains_keyword_dump(normalized):
        violations.append("keyword-dump formatting (slash/parenthetical list)")

    if _BANNED_MARKETING_WORDS.search(normalized):
        violations.append("contains banned marketing language")

    for pattern in _GENERIC_BOILERPLATE_PATTERNS:
        if pattern.search(normalized):
            violations.append("generic boilerplate phrasing")
            break

    base_lower = base_description.lower()
    for pattern in _UNVERIFIABLE_PATTERNS:
        match = pattern.search(normalized)
        if match and match.group(0).lower() not in base_lower:
            violations.append(
                f"unverifiable claim not present in base description: '{match.group(0)}'"
            )
            break

    anchor_terms = _extract_anchor_terms(base_description)
    if anchor_terms:
        sentence_lower = normalized.lower()
        if not any(anchor in sentence_lower for anchor in anchor_terms):
            violations.append("missing product-specific anchor term")

    return violations


def normalize_and_validate_finish_sentences(
    *,
    raw: object,
    finish_names: Iterable[str],
    base_description: str,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Normalize canonical finish keys and validate sentence quality.

    Returns:
        (accepted_sentences, rejected_by_finish)
    """
    if not isinstance(raw, dict):
        return {}, {"__payload__": ["not a JSON object"]}

    accepted: dict[str, str] = {}
    rejected: dict[str, list[str]] = {}

    for finish in finish_names:
        value = raw.get(finish)
        if not isinstance(value, str):
            rejected[finish] = ["missing or non-string sentence"]
            continue
        sentence = value.strip()
        violations = validate_finish_sentence(
            finish_name=finish,
            sentence=sentence,
            base_description=base_description,
        )
        if violations:
            rejected[finish] = violations
            continue
        accepted[finish] = sentence

    return accepted, rejected
