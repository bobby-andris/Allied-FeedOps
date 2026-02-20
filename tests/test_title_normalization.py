from feedops.pipeline import title_normalization as title_module


def test_known_collection_moves_before_brand_when_brand_present(monkeypatch):
    monkeypatch.setattr(
        title_module,
        "is_known_collection_name",
        lambda name: str(name).strip().lower() == "dottingham",
    )

    title = "Allied Brass, 24-Inch Wall Mount Towel Bar, Dottingham Collection, Solid Brass"
    normalized = title_module.normalize_title_separators(title)

    assert normalized.endswith("Dottingham Collection, Allied Brass")
    assert "24-Inch Wall Mount Towel Bar" in normalized


def test_collection_order_unchanged_when_brand_absent(monkeypatch):
    monkeypatch.setattr(title_module, "is_known_collection_name", lambda _name: True)

    title = "Dottingham Collection, 24-Inch Wall Mount Towel Bar"
    normalized = title_module.normalize_title_separators(title)

    assert normalized == "Dottingham Collection, 24-Inch Wall Mount Towel Bar"


def test_unknown_collection_segment_is_removed(monkeypatch):
    monkeypatch.setattr(title_module, "is_known_collection_name", lambda _name: False)

    title = "24-Inch Wall Mount Towel Bar, Random Collection, Allied Brass"
    normalized = title_module.normalize_title_separators(title)

    assert normalized == "24-Inch Wall Mount Towel Bar, Allied Brass"
