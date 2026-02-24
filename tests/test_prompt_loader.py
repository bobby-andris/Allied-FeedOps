import hashlib

from feedops.api import prompt_loader
from feedops.pipeline.prompts import SYSTEM_PROMPT


def test_get_system_prompt_includes_canonical_base(monkeypatch):
    """get_system_prompt() includes SYSTEM_PROMPT as its base."""
    monkeypatch.setattr(
        prompt_loader,
        "load_active_prompt_template",
        lambda: {"system_prompt": "DB prompt that should be ignored"},
    )

    result = prompt_loader.get_system_prompt()
    assert result.startswith(SYSTEM_PROMPT[:100])


def test_get_system_prompt_hash_is_stable():
    """Hash is deterministic for the same prompt content."""
    h1 = prompt_loader.get_system_prompt_hash()
    h2 = prompt_loader.get_system_prompt_hash()
    assert h1 == h2
    assert len(h1) == 16


def test_format_gold_standard_examples_bundle_formats_cross_platform_examples(monkeypatch):
    monkeypatch.setattr(
        prompt_loader,
        "load_active_prompt_template",
        lambda: {
            "gold_standard_examples": {
                "examples": [
                    {
                        "category": "Towel Bars",
                        "gold_standard_content": {
                            "google_title": "24-Inch Wall Mount Towel Bar, Solid Brass, Satin Nickel, Allied Brass",
                            "google_description": "Solid brass towel bar for lasting performance. " * 20,
                            "shopify_title": "Foobar Collection Towel Bar 24-Inch - Wall Mount",
                            "shopify_description": "<p>Designed for daily use.</p>" * 10,
                            "why_it_works": "Leads with product type + size and supports with evidence-backed claims.",
                        },
                    }
                ]
            }
        },
    )

    rendered = prompt_loader.format_gold_standard_examples_bundle(max_examples=1)
    assert "Example 1 (Towel Bars):" in rendered
    assert "Google title:" in rendered
    assert "Google description:" in rendered
    assert "Shopify title:" in rendered
    assert "Shopify description:" in rendered
    assert "Why it works:" in rendered
