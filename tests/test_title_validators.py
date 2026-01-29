from feedops.pipeline.validators import validate_title_structure


def test_validate_title_structure_accepts_hyphen_separator():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar - Solid Brass - Allied Brass",
        field="google_title",
    )
    assert not any("separator" in w.lower() for w in warnings)


def test_validate_title_structure_accepts_comma_separator():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar, Solid Brass, Allied Brass",
        field="google_title",
    )
    assert not any("separator" in w.lower() for w in warnings)


def test_validate_title_structure_warns_when_no_separator_present():
    warnings = validate_title_structure(
        "18-Inch Wall Mount Towel Bar Solid Brass Allied Brass",
        field="google_title",
    )
    assert any("separator" in w.lower() for w in warnings)

