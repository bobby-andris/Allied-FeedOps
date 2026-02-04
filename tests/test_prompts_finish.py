from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_system_prompt_calls_out_finish_neutral_master_descriptions() -> None:
    assert "MasterSKU descriptions are finish-neutral" in SYSTEM_PROMPT


def test_system_prompt_includes_competitor_finish_patterns() -> None:
    assert "Competitor patterns" in SYSTEM_PROMPT
