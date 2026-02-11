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
    re.compile(
        r"(?i)\bchoose from (?:a wide variety of )?(?:lifetime )?"
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


def strip_hardcoded_finish_names(content: str, finish_names: list[str]) -> str:
    """Remove explicit finish names from base descriptions.

    Google/Bing base descriptions must stay finish-agnostic before variant expansion.
    """
    text = (content or "").strip()
    if not text:
        return ""

    for finish_name in finish_names:
        escaped = re.escape(finish_name)
        text = re.sub(rf"(?i)\b{escaped}\b", "", text)

    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\(\s*\)", "", text)
    return text.strip(" ,")


def build_fallback_finish_sentences(finish_names: list[str]) -> dict[str, str]:
    """Create deterministic finish sentences when model generation is unavailable."""
    return {
        finish_name: f"The {finish_name} finish complements this product's design."
        for finish_name in finish_names
    }


def inject_finish_sentence_placeholder(content: str) -> str:
    """Ensure a base variant description contains `{FINISH_SENTENCE}` exactly once.

    The placeholder is inserted after the first sentence when possible so downstream
    variant expansion can splice product+finish-specific copy naturally.
    """
    text = (content or "").strip()
    if not text:
        return FINISH_SENTENCE_PLACEHOLDER

    placeholder_count = text.count(FINISH_SENTENCE_PLACEHOLDER)
    if placeholder_count == 1:
        return text
    if placeholder_count > 1:
        text = re.sub(r"\s*\{FINISH_SENTENCE\}\s*", " ", text).strip()
        text = re.sub(r"\s{2,}", " ", text)
        return inject_finish_sentence_placeholder(text)

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
