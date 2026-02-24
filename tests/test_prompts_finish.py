from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_system_prompt_calls_out_finish_neutral_master_descriptions() -> None:
    # Shopify fields are finish-agnostic per platform_rules and output_contract
    assert "finish-agnostic" in SYSTEM_PROMPT


def test_system_prompt_includes_competitor_material_prohibition() -> None:
    # Competitor materials must be prohibited (renamed from competitor_finish_patterns)
    assert "die-cast zinc" in SYSTEM_PROMPT
