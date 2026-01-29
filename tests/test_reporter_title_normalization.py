from feedops.pipeline.reporter import _normalize_title_separators


def test_normalize_title_separators_removes_empty_segments():
    title = "Towel Bar, 30-Inch, Solid Brass, Carolina Collection, , Allied Brass"
    assert _normalize_title_separators(title) == (
        "Towel Bar, 30-Inch, Solid Brass, Carolina Collection, Allied Brass"
    )


def test_normalize_title_separators_removes_dangling_hyphen_segment():
    title = "Carolina Collection 30-Inch Towel Bar (Solid Brass, Wall Mount) -, Allied Brass"
    assert _normalize_title_separators(title) == (
        "Carolina Collection 30-Inch Towel Bar (Solid Brass, Wall Mount), Allied Brass"
    )


def test_normalize_title_separators_converts_pipes_to_commas():
    title = "Towel Bar 30-Inch | Solid Brass | Allied Brass"
    assert _normalize_title_separators(title) == "Towel Bar 30-Inch, Solid Brass, Allied Brass"


def test_normalize_title_separators_drops_unknown_collection_segments():
    title = "Paper Towel Holder, Brass Paper Towel Holders Collection, Allied Brass"
    assert _normalize_title_separators(title) == "Paper Towel Holder, Allied Brass"
