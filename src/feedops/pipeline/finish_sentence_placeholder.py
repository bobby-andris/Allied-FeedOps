"""Utilities for normalizing base descriptions with finish sentence placeholders."""

from __future__ import annotations

import re

FINISH_SENTENCE_PLACEHOLDER = "{FINISH_SENTENCE}"
_SENTENCE_BREAK_PATTERN = re.compile(r"(?<!\d)\.(?!\d)")


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

