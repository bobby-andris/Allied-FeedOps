from feedops.pipeline.evidence import (
    format_evidence_markdown,
    sanitize_catalog_prose,
    sanitize_evidence_value,
    sanitize_prompt_text,
)
import inspect

from feedops.api.prompt_builder import build_google_prompt
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.generator import _platform_completion_cap, generate_per_platform
from feedops.pipeline.prompts import (
    BING_BRIEF,
    BING_SCHEMA,
    GOOGLE_BRIEF,
    GOOGLE_SCHEMA,
    SHOPIFY_SCHEMA,
    SYSTEM_PROMPT,
)
from feedops.pipeline.skill_loader import get_platform_system_prompt
from feedops.pipeline.enrichment import Evidence


def test_sanitize_prompt_text_removes_competitor_brands() -> None:
    raw = "Compared to Jan Barboglio and MOEN designs, this option is clean."
    cleaned = sanitize_prompt_text(raw, strip_competitor_brands=True)

    lowered = cleaned.lower()
    assert "jan barboglio" not in lowered
    assert "moen" not in lowered
    assert "designs" in lowered


def test_sanitize_catalog_prose_removes_banned_words_preserves_placeholders() -> None:
    raw = "A finest premium option that still supports {FINISH_SENTENCE} naturally."
    cleaned = sanitize_catalog_prose(raw)

    lowered = cleaned.lower()
    assert "finest" not in lowered
    assert "premium" not in lowered
    assert "{FINISH_SENTENCE}" in cleaned


def test_sanitize_evidence_value_applies_keyword_brand_filtering() -> None:
    raw_keyword_value = "jan barboglio paper towel holder, moen wall hook"
    cleaned = sanitize_evidence_value(
        "search_queries_top",
        raw_keyword_value,
        source="search_queries",
    )
    lowered = cleaned.lower()
    assert "jan barboglio" not in lowered
    assert "moen" not in lowered
    assert "paper towel holder" in lowered


def test_copy_context_evidence_markdown_excludes_metadata_and_search_rows() -> None:
    rows = [
        Evidence(field="material", value="Solid Brass", source="material"),
        Evidence(field="gtin", value="123456789", source="gtin"),
        Evidence(field="category", value="Towel Bars", source="category"),
        Evidence(
            field="search_queries_top",
            value='"paper towel holder" (2.4K vol)',
            source="search_insights",
        ),
    ]

    markdown = format_evidence_markdown(rows, for_customer_copy=True)
    lowered = markdown.lower()
    assert "solid brass" in lowered
    assert "| gtin |" not in lowered
    assert "| category |" not in lowered
    assert "| search_queries_top |" not in lowered


def test_schema_contract_keeps_soft_length_for_descriptions() -> None:
    google_description = GOOGLE_SCHEMA["properties"]["google_description"]
    bing_description = BING_SCHEMA["properties"]["bing_description"]

    assert google_description["minLength"] == 700
    assert "maxLength" not in google_description
    assert "pattern" not in google_description

    assert bing_description["minLength"] == 700
    assert "maxLength" not in bing_description
    assert "pattern" not in bing_description


def test_schema_contract_keeps_hard_max_for_platform_enforced_fields() -> None:
    assert GOOGLE_SCHEMA["properties"]["google_title"]["maxLength"] == 150
    assert GOOGLE_SCHEMA["properties"]["google_short_title"]["maxLength"] == 70
    assert SHOPIFY_SCHEMA["properties"]["shopify_meta_description"]["maxLength"] == 160


def test_finish_completion_cap_floor_for_runtime_generation() -> None:
    assert _platform_completion_cap("finish", 4000) == 10000
    assert _platform_completion_cap("google", 4000) == 4000


def test_runtime_generation_default_completion_cap_is_quality_safe() -> None:
    signature = inspect.signature(generate_per_platform)
    assert signature.parameters["max_completion_tokens"].default == 8000


def test_prompt_contract_bans_promo_words_globally() -> None:
    # Banned words must appear in SYSTEM_PROMPT (in the brand_voice section)
    assert "finest, luxurious, premium, exclusive" in SYSTEM_PROMPT


def test_prompt_contract_bans_towel_rack_in_google_towel_bar_titles() -> None:
    assert 'NEVER include the phrase "towel rack" in Google title text' in GOOGLE_BRIEF


def test_bing_brief_explicitly_bans_promo_words() -> None:
    assert "Also ban promo words in customer-facing copy" in BING_BRIEF


def test_bing_brief_bans_towel_rack_in_towel_bar_titles() -> None:
    assert 'NEVER "Towel Rack" in title' in BING_BRIEF


def test_google_and_bing_briefs_define_finish_sentence_examples() -> None:
    assert "Good flow:" in GOOGLE_BRIEF
    assert "Anti-example:" in GOOGLE_BRIEF
    assert "Good flow:" in BING_BRIEF
    assert "Anti-example:" in BING_BRIEF


def test_bing_brief_uses_conditional_synonym_language() -> None:
    assert "Use synonym variants conditionally, never by quota." in BING_BRIEF


def test_platform_system_prompt_isolation_google_excludes_shopify_html_rules() -> None:
    google_prompt = get_platform_system_prompt("google")
    assert "Shopify description: HTML required" not in google_prompt
    assert "<platform_rules>" in google_prompt
    assert "Google fields only" in google_prompt


def test_platform_system_prompt_isolation_shopify_excludes_google_variant_placeholders() -> None:
    shopify_prompt = get_platform_system_prompt("shopify")
    assert "{FINISH_SENTENCE}" not in shopify_prompt
    assert "{FINISH_NAME}" not in shopify_prompt
    assert "<platform_rules>" in shopify_prompt
    assert "Shopify fields only" in shopify_prompt


def test_google_prompt_wraps_keyword_section_as_enrichment_hint() -> None:
    sku = ParentSKU(
        master_sku="TEST-KEYWORD-1",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline 24-Inch Towel Bar",
        current_description="Wall-mounted towel bar with classic skyline styling.",
    )
    prompt = build_google_prompt(
        sku_data=sku,
        evidence=None,
        keywords="Primary anchor: 24-inch towel bar",
        category_guidance="",
        gold_examples="",
    )
    assert "<keyword_enrichment_hints>" in prompt
    assert "If a hint conflicts with product truth" in prompt


def test_generator_v2_imports_only_platform_specific_builders() -> None:
    """generator.py must use build_google_prompt etc., never build_core_prompt."""
    import feedops.pipeline.generator as gen_module
    source = inspect.getsource(gen_module)
    assert "build_google_prompt" in source
    assert "build_bing_prompt" in source
    assert "build_shopify_prompt" in source
    assert "build_core_prompt" not in source


def test_ab_harness_imports_only_platform_specific_builders() -> None:
    """ab_prompt_test.py must NOT import build_core_prompt (the v1 legacy path)."""
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "ab_prompt_test.py"
    source = script_path.read_text()
    assert "build_core_prompt" not in source, (
        "ab_prompt_test.py must not import build_core_prompt — "
        "use build_google_prompt/build_bing_prompt/build_shopify_prompt instead"
    )
    assert "build_google_prompt" in source
    assert "build_bing_prompt" in source
    assert "build_shopify_prompt" in source
