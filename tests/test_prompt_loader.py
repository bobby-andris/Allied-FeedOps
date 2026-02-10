import hashlib

from feedops.api import prompt_loader
from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_get_system_prompt_ignores_db_system_prompt(monkeypatch):
    monkeypatch.setattr(
        prompt_loader,
        "load_active_prompt_template",
        lambda: {"system_prompt": "DB prompt that should be ignored"},
    )

    assert prompt_loader.get_system_prompt() == SYSTEM_PROMPT


def test_get_system_prompt_hash_matches_canonical_prompt():
    expected = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]
    assert prompt_loader.get_system_prompt_hash() == expected
