from feedops.quality.collection_badge import get_collection_badge


def test_collection_badge_none_when_missing() -> None:
    badge = get_collection_badge(None)
    assert badge.kind == "none"
    assert badge.collection is None


def test_collection_badge_designer_when_curated_name() -> None:
    badge = get_collection_badge("Argo")
    assert badge.kind == "designer"
    assert badge.collection == "Argo"


def test_collection_badge_merchandising_when_unknown_name() -> None:
    badge = get_collection_badge("Brass Paper Towel Holders")
    assert badge.kind == "merchandising"
    assert badge.collection == "Brass Paper Towel Holders"

