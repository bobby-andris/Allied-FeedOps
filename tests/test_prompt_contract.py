from feedops.api import prompt_loader
from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_system_prompt_uses_required_section_contracts() -> None:
    required_sections = [
        "<creative_direction>",
        "<objective_hierarchy>",
        "<brand_voice>",
        "<accuracy_guardrail>",
        "<output_contract>",
    ]
    for section in required_sections:
        assert section in SYSTEM_PROMPT, f"Missing section: {section}"


def test_system_prompt_removes_clickbait_conflict_language() -> None:
    disallowed_phrases = [
        "Make them want to click",
        "Make them click",
        "write for humans first",
    ]
    prompt_lower = SYSTEM_PROMPT.lower()
    for phrase in disallowed_phrases:
        assert phrase.lower() not in prompt_lower


def test_system_prompt_size_fits_ci_budget() -> None:
    assert len(SYSTEM_PROMPT) <= prompt_loader.SYSTEM_PROMPT_CI_MAX_CHARS


def test_get_system_prompt_warns_when_threshold_exceeded(monkeypatch) -> None:
    messages: list[str] = []

    class _LoggerStub:
        def warning(self, msg: str, *args) -> None:
            messages.append(msg % args if args else msg)

        def info(self, msg: str, *args) -> None:
            pass

        def debug(self, msg: str, *args) -> None:
            pass

    monkeypatch.setattr(prompt_loader, "CANONICAL_SYSTEM_PROMPT", "x" * 280_001)
    monkeypatch.setattr(prompt_loader, "_prompt_size_warning_emitted", False)
    monkeypatch.setattr(prompt_loader, "logger", _LoggerStub())

    prompt_loader.get_system_prompt()
    assert any("SYSTEM_PROMPT length is" in msg for msg in messages)
