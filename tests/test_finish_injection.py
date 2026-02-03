import pytest

from feedops.pipeline.finish_injection import (
    generate_variant_description,
    generate_variant_title,
)


def _base_description() -> str:
    return (
        "Keep towels dry and within reach with this wall mount towel bar.\n\n"
        "Highlights:\n"
        "- Handles daily use with reliable support\n"
        "- Concealed mounting hardware keeps the look clean\n"
        "- Coordinates with matching accessories\n\n"
        "Specs:\n"
        "Length: 24 in\n"
    )


def test_generate_variant_title_moves_finish_after_first_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    base_title = "Towel Ring 6-Inch | Waverly Place | Allied Brass"
    result = generate_variant_title(base_title, "Polished Nickel")
    assert result == "Towel Ring 6-Inch | Polished Nickel | Waverly Place | Allied Brass"


def test_generate_variant_title_moves_finish_into_first_segment_when_finish_would_be_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    base_title = (
        "24-Inch Wall Mount Towel Bar, Solid Brass, Concealed Mount, Waverly Place Collection "
        "| Allied Brass"
    )
    result = generate_variant_title(base_title, "Satin Nickel")
    assert result.startswith("Satin Nickel ")
    assert " | Satin Nickel | " not in result
    assert result.endswith("| Allied Brass")


def test_variant_description_finish_in_opening_and_no_finish_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finish should appear early in description (within first ~200 chars).

    The new approach adds finish as a separate short sentence rather than
    appending a long clause to the first sentence. This creates more
    readable output.
    """
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    result = generate_variant_description(
        base_description=_base_description(),
        finish_name="Polished Nickel",
        collection_name="Waverly Place",
        collection_group="Transitional",
        platform="google",
    )
    # Finish should appear early in description (within first ~200 chars)
    opening = result[:200]
    assert "Polished Nickel" in opening
    # Should not have verbose "About This Finish" block
    assert "About This Finish" not in result
    # Should have finish-related bullet
    bullet_lines = [line for line in result.splitlines() if line.strip().startswith("- ")]
    assert any("Polished Nickel" in line for line in bullet_lines)


def test_variant_description_respects_kitchen_room_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    base_description = (
        "Keep paper towels within reach without sacrificing kitchen counter space.\n\n"
        "Highlights:\n"
        "- Easy tear, one-handed use\n"
        "- Stable wall-mounted design\n\n"
        "Specs:\n"
        "Projection: 3 in\n"
    )
    result = generate_variant_description(
        base_description=base_description,
        finish_name="Satin Nickel",
        category="Paper Towel Holders",
        room_context="kitchen",
        platform="google",
    )
    assert "bathroom" not in result.lower()


def test_variant_description_adds_finish_count_bullet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    result = generate_variant_description(
        base_description=_base_description(),
        finish_name="Polished Nickel",
        finish_count=28,
        material="Solid Brass",
        platform="google",
    )
    bullet_lines = [line for line in result.splitlines() if line.strip().startswith("- ")]
    assert any("28" in line and "finish" in line.lower() for line in bullet_lines)


def test_variant_description_does_not_leave_dangling_finish_options_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    base_description = (
        "Keep towels dry and within reach with this wall mount towel bar.\n\n"
        "Highlights:\n"
        "- Reliable support for daily use\n\n"
        "Specs:\n"
        "- Finish options: multiple designer finish options available\n"
        "- Warranty: Limited Lifetime Warranty\n"
    )
    result = generate_variant_description(
        base_description=base_description,
        finish_name="Antique Brass",
        collection_name="Carolina",
        collection_group="Traditional",
        platform="google",
        size="18 Inch",
    )
    assert "multiple designer finish options available" not in result
    assert "Finish options:" not in result
