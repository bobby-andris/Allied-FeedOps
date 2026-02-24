from feedops.pipeline.prompts import SHOPIFY_BRIEF, SYSTEM_PROMPT


def test_system_prompt_calls_out_finish_neutral_master_descriptions() -> None:
    # Shopify brief is finish-agnostic by design.
    assert "finish-agnostic" in SHOPIFY_BRIEF


def test_system_prompt_includes_competitor_material_prohibition() -> None:
    # Competitor materials must be prohibited (renamed from competitor_finish_patterns)
    assert "die-cast zinc" in SYSTEM_PROMPT
