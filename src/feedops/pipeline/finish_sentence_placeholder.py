"""Utilities for normalizing base descriptions with finish sentence placeholders."""

from __future__ import annotations

import re

FINISH_SENTENCE_PLACEHOLDER = "{FINISH_SENTENCE}"
_SENTENCE_BREAK_PATTERN = re.compile(r"(?<!\d)\.(?!\d)")
_GENERIC_FINISH_COUNT_PATTERNS = [
    re.compile(
        r"(?i)\bfinish options:\s*available in[^.!\n]*(?:designer\s+)?finishes[^.!\n]*[.!]?"
    ),
    re.compile(
        r"(?i)\bavailable in (?:a wide variety of )?(?:lifetime )?"
        r"(?:multiple|\d+)\s+(?:designer\s+)?finishes[^.!\n]*[.!]?"
    ),
    re.compile(r"(?i)\bmultiple designer finish options available\b[.!]?"),
]


def strip_generic_finish_count_claims(content: str) -> str:
    """Remove generic finish-count claims from base descriptions.

    These phrases are not variant-specific and cause parity drift when a base
    description later receives finish sentence expansion.
    """
    text = (content or "").strip()
    if not text:
        return ""

    for pattern in _GENERIC_FINISH_COUNT_PATTERNS:
        text = pattern.sub(" ", text)

    # Normalize punctuation/spacing left by removals.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\.\s*\.", ".", text)
    return text.strip()


def inject_finish_sentence_placeholder(content: str) -> str:
    """Ensure a base variant description contains `{FINISH_SENTENCE}` exactly once.

    The placeholder is inserted after the first sentence when possible so downstream
    variant expansion can splice product+finish-specific copy naturally.
    """
    text = (content or "").strip()
    if not text:
        return FINISH_SENTENCE_PLACEHOLDER

    if FINISH_SENTENCE_PLACEHOLDER in text:
        return text

    match = _SENTENCE_BREAK_PATTERN.search(text)
    if match:
        insert_at = match.end()
        before = text[:insert_at].rstrip()
        after = text[insert_at:].lstrip()
        if after:
            return f"{before} {FINISH_SENTENCE_PLACEHOLDER} {after}".strip()
        return f"{before} {FINISH_SENTENCE_PLACEHOLDER}".strip()

    return f"{text} {FINISH_SENTENCE_PLACEHOLDER}".strip()


def normalize_base_description_with_finish_placeholder(content: str) -> str:
    """Sanitize and ensure `{FINISH_SENTENCE}` appears exactly once."""
    sanitized = strip_generic_finish_count_claims(content)
    return inject_finish_sentence_placeholder(sanitized)
