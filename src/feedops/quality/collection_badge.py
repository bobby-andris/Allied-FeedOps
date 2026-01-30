from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from feedops.pipeline.collection_descriptions import is_known_collection_name


CollectionBadgeKind = Literal["none", "designer", "merchandising"]


@dataclass(frozen=True)
class CollectionBadge:
    kind: CollectionBadgeKind
    collection: str | None
    message: str


def get_collection_badge(collection: str | None) -> CollectionBadge:
    value = (collection or "").strip()
    if not value:
        return CollectionBadge(
            kind="none",
            collection=None,
            message="No designer collection available (collection should not be used in titles).",
        )
    if is_known_collection_name(value):
        return CollectionBadge(
            kind="designer",
            collection=value,
            message=f"Designer collection (validated): {value} — allowed in titles.",
        )
    return CollectionBadge(
        kind="merchandising",
        collection=value,
        message=f"Non-designer/merchandising collection: {value} — exclude from titles.",
    )

