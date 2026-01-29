from feedops.pipeline.validators import validate_variant_title_uniqueness


def test_flags_finish_position_when_finish_is_past_visible_zone():
    titles = [
        "24-Inch Wall Mount Towel Bar, Solid Brass, Concealed Mount, Waverly Place Collection, Allied Brass, Satin Nickel",
        "24-Inch Wall Mount Towel Bar, Solid Brass, Concealed Mount, Waverly Place Collection, Allied Brass, Polished Chrome",
    ]
    warnings = validate_variant_title_uniqueness(titles)
    assert any("finish" in w.lower() for w in warnings)


def test_flags_exact_duplicate_titles():
    titles = [
        "Polished Nickel Paper Towel Holder, Wall Mount, Allied Brass",
        "Polished Nickel Paper Towel Holder, Wall Mount, Allied Brass",
    ]
    warnings = validate_variant_title_uniqueness(titles)
    assert any("duplicate" in w.lower() for w in warnings)

