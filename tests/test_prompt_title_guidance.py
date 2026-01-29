from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_system_prompt_title_guidance_does_not_require_pipe_separators():
    assert "Use pipe separators" not in SYSTEM_PROMPT
    assert "preceded by a pipe" not in SYSTEM_PROMPT

