"""Shared title normalization helpers for channel-ready content."""

from __future__ import annotations

from feedops.pipeline.collection_descriptions import is_known_collection_name


def normalize_title_separators(title: str) -> str:
    """Normalize separators for readability and policy compliance.

    - Convert pipes to commas (avoid symbol-heavy separators).
    - Remove empty segments and dangling punctuation.
    - Ensure 'Allied Brass' appears once as the last segment when present.
    - When present with brand, move known collection name to segment before brand.
    """
    raw = (title or "").strip()
    if not raw:
        return ""

    cleaned = raw.replace("|", ",")
    parts = []
    saw_brand = False
    for chunk in cleaned.split(","):
        part = chunk.strip().strip("-–—").strip()
        if not part:
            continue
        if part.lower().endswith(" collection"):
            name = part[: -len(" collection")].strip()
            if not is_known_collection_name(name):
                continue
            part = f"{name} Collection"
        if part.lower() == "allied brass":
            saw_brand = True
            continue
        parts.append(part)

    if saw_brand:
        collection_segments = [p for p in parts if p.lower().endswith(" collection")]
        if collection_segments:
            parts = [p for p in parts if not p.lower().endswith(" collection")]
            parts.append(collection_segments[-1])
        parts.append("Allied Brass")

    return ", ".join(parts).strip(" ,")


def trim_title_to_length(title: str, max_len: int) -> str:
    """Trim a comma-separated title to max_len while preserving readability."""
    cleaned = normalize_title_separators(title)
    if len(cleaned) <= max_len:
        return cleaned

    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    brand = None
    if parts and parts[-1].lower() == "allied brass":
        brand = parts.pop()

    while parts and len(", ".join(parts + ([brand] if brand else []))) > max_len:
        if len(parts) <= 1:
            break
        parts.pop()

    rebuilt = ", ".join(parts + ([brand] if brand else []))
    if len(rebuilt) <= max_len:
        return rebuilt.strip(" ,")

    suffix = f", {brand}" if brand else ""
    budget = max_len - len(suffix)
    head = ", ".join(parts)
    head = head[: max(budget, 0)].rstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0].rstrip()
    if suffix and head.endswith(","):
        head = head.rstrip(", ").rstrip()
    final = f"{head}{suffix}" if head else (brand or "")
    return final.strip()[:max_len].strip(" ,")

