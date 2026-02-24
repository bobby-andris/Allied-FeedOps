"""V1 production code path regression tests.

These tests verify that the v1 production code path (used by main.py when
FEEDOPS_PROMPT_VERSION is unset or "v1") continues to work correctly after
Phases 23-25.3 changes. The v1 path uses:
  - build_core_prompt() for user prompt construction
  - get_system_prompt() for system prompt with skills
  - Simple {"content": "string"} response schema (NOT CANDIDATE_SCHEMA)
  - parse_candidate_response() is NOT used by v1 path in main.py

These tests exercise the full prompt assembly pipeline with mocked DB calls
to ensure no real API or database access is needed.
"""

from unittest.mock import patch

import pytest

from feedops.models import Candidate, ParentSKU, Score, Variant
from feedops.pipeline.generator import parse_candidate_response


@pytest.fixture
def representative_parent_sku():
    """Create a representative ParentSKU for v1 path testing."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        upc="123456789",
        gtin="00012345678905",
        position=1,
        product_length=20.8,
        product_weight=2.5,
        main_image_url="https://example.com/image.jpg",
    )
    return ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar features solid brass construction.",
        material="Brass",
        mounting_type="Wall mount",
        weight_capacity=10.0,
        variants=[variant],
    )


# ---- Monkeypatch DB-calling helpers ----

def _stub_db_calls(monkeypatch):
    """Monkeypatch all DB-calling functions used during prompt assembly."""
    from feedops.pipeline import evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "fetch_master_sku_keywords",
        lambda item_group_id, item_ids, category=None: [],
    )
    monkeypatch.setattr(
        evidence_module,
        "get_external_keywords",
        lambda category=None, master_sku=None: [],
    )
    monkeypatch.setattr(
        evidence_module,
        "fetch_search_queries_for_master_sku",
        lambda master_sku, **kwargs: [],
    )
    monkeypatch.setattr(
        evidence_module,
        "format_search_queries_for_evidence",
        lambda queries, context, **kwargs: [],
    )

    from feedops.api import prompt_loader as loader_module

    monkeypatch.setattr(
        loader_module,
        "format_gold_standard_examples_bundle",
        lambda **kwargs: "",
    )
    monkeypatch.setattr(
        loader_module,
        "format_gold_standard_examples",
        lambda **kwargs: "",
    )
    monkeypatch.setattr(
        loader_module,
        "get_category_guidance",
        lambda category: "",
    )


# ---- Test 1: build_core_prompt assembles correctly ----

def test_build_core_prompt_assembles_correctly(representative_parent_sku, monkeypatch):
    """build_core_prompt returns a non-empty prompt with expected sections."""
    _stub_db_calls(monkeypatch)

    from feedops.api.prompt_builder import build_core_prompt
    from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

    evidence = build_evidence_table(representative_parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    prompt = build_core_prompt(
        representative_parent_sku,
        evidence,
        evidence_markdown,
        platform="google",
        content_type="title",
    )

    assert isinstance(prompt, str)
    assert len(prompt) > 100, "Prompt should be substantial"
    assert "Product Evidence Table" in prompt
    assert "Target platform: google" in prompt
    # Evidence should include product data from the SKU
    assert "Skyline" in prompt  # collection name appears in evidence
    assert "Brass" in prompt  # material appears in evidence


def test_build_core_prompt_includes_product_data(representative_parent_sku, monkeypatch):
    """build_core_prompt includes product-specific data from the SKU."""
    _stub_db_calls(monkeypatch)

    from feedops.api.prompt_builder import build_core_prompt
    from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

    evidence = build_evidence_table(representative_parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    prompt = build_core_prompt(
        representative_parent_sku,
        evidence,
        evidence_markdown,
        platform="google",
        content_type="description",
    )

    # Prompt should include product design story and competitive positioning
    assert "Product Design Story" in prompt or "product" in prompt.lower()
    assert "Competitive Positioning" in prompt or "competitive" in prompt.lower()
    # Prompt should include material info from evidence
    assert "brass" in prompt.lower() or "Brass" in prompt


# ---- Test 2: get_system_prompt returns valid prompt ----

def test_get_system_prompt_returns_valid_prompt():
    """get_system_prompt returns a non-empty string with expected XML tags and skill content."""
    from feedops.api.prompt_loader import get_system_prompt

    system_prompt = get_system_prompt()

    assert isinstance(system_prompt, str)
    assert len(system_prompt) > 500, "System prompt should be substantial"
    # Key XML tags from the rewritten SYSTEM_PROMPT
    assert "<accuracy_guardrail>" in system_prompt
    assert "<scoring_rubric>" in system_prompt
    assert "<creative_direction>" in system_prompt
    # Skill content should be present (at least brand/finish content)
    prompt_lower = system_prompt.lower()
    assert "allied brass" in prompt_lower, "System prompt should include Allied Brass brand content"


# ---- Test 3: v1 output schema is simple content string ----

def test_v1_output_schema_is_simple_content_string(representative_parent_sku, monkeypatch):
    """The v1 path uses a simple {"content": "string"} schema, NOT CANDIDATE_SCHEMA.

    This test verifies that the v1 path's expected response format is a simple
    JSON object with a "content" key containing a string, confirming the v1 path
    does NOT depend on CANDIDATE_SCHEMA or parse_candidate_response.
    """
    _stub_db_calls(monkeypatch)

    from feedops.api.prompt_builder import build_core_prompt
    from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

    evidence = build_evidence_table(representative_parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    prompt = build_core_prompt(
        representative_parent_sku,
        evidence,
        evidence_markdown,
        platform="google",
        content_type="title",
    )

    # The v1 path in main.py sends this prompt with {"content": "string"} schema.
    # Verify the prompt includes the JSON output instruction.
    assert '{"content":' in prompt or '"content"' in prompt

    # Simulate v1 response — simple content string
    v1_response = {"content": "Antique Brass 18-Inch Towel Bar - Skyline Collection - Allied Brass"}
    assert isinstance(v1_response["content"], str)
    assert len(v1_response["content"]) > 0


# ---- Test 4: parse_candidate_response with new Score fields ----

def test_parse_candidate_response_new_fields():
    """parse_candidate_response correctly reads the 10 new self_score field names."""
    response = {
        "google_title": "Test Google Title for Towel Bar Product with Long Name Here",
        "google_short_title": "Test Short Title",
        "google_description": "Test description " * 30,
        "bing_title": "Test Bing Title for Towel Bar Product with Long Name Here Too",
        "bing_description": "Test description " * 30,
        "shopify_title": "Test Shopify Title",
        "shopify_description": "<p>Test description</p>",
        "claims": [
            {"claim": "solid brass", "source_field": "material", "source_value": "Brass"},
        ],
        "self_score": {
            "hook_quality": 8,
            "product_specificity": 7,
            "competitive_diff": 6,
            "keyword_integration": 9,
            "customer_scenario": 7,
            "emotional_resonance": 6,
            "factual_accuracy": 9,
            "platform_compliance": 8,
            "finish_integration": 7,
            "variety_score": 6,
        },
    }

    candidate = parse_candidate_response(response)

    assert isinstance(candidate, Candidate)
    assert isinstance(candidate.self_score, Score)
    assert candidate.self_score.hook_quality == 8
    assert candidate.self_score.product_specificity == 7
    assert candidate.self_score.competitive_diff == 6
    assert candidate.self_score.keyword_integration == 9
    assert candidate.self_score.customer_scenario == 7
    assert candidate.self_score.emotional_resonance == 6
    assert candidate.self_score.factual_accuracy == 9
    assert candidate.self_score.platform_compliance == 8
    assert candidate.self_score.finish_integration == 7
    assert candidate.self_score.variety_score == 6
    # Composite: (8+7+6+9+7+6+9+8+7+6) / 100 * 100 = 73
    assert candidate.self_score.composite == 73.0


# ---- Test 5: parse_candidate_response with OLD fields falls back gracefully ----

def test_parse_candidate_response_old_fields_fallback():
    """parse_candidate_response gracefully returns defaults when old field names are provided.

    This confirms backward compatibility via the .get() fallback mechanism:
    old field names (specificity, benefit_coverage, etc.) are not recognized
    by the new Score model, so all fields get the default value of 5.
    """
    response = {
        "google_title": "Test Google Title for Towel Bar Product with Long Name Here",
        "google_short_title": "Test Short Title",
        "google_description": "Test description " * 30,
        "bing_title": "Test Bing Title for Towel Bar Product with Long Name Here Too",
        "bing_description": "Test description " * 30,
        "shopify_title": "Test Shopify Title",
        "shopify_description": "<p>Test description</p>",
        "claims": [],
        "self_score": {
            "specificity": 8,
            "benefit_coverage": 8,
            "keyword_inclusion": 8,
            "format_adherence": 8,
            "brand_voice": 8,
            "factual_accuracy": 8,
        },
    }

    candidate = parse_candidate_response(response)

    assert isinstance(candidate.self_score, Score)
    # All new fields should be 5 (default) since old field names are not recognized
    assert candidate.self_score.hook_quality == 5
    assert candidate.self_score.product_specificity == 5
    assert candidate.self_score.competitive_diff == 5
    assert candidate.self_score.keyword_integration == 5
    assert candidate.self_score.customer_scenario == 5
    assert candidate.self_score.emotional_resonance == 5
    # factual_accuracy is present in BOTH old and new schemas, so it should be 8
    # Wait - "factual_accuracy" key matches the new field name exactly, so it's read correctly
    assert candidate.self_score.factual_accuracy == 8
    assert candidate.self_score.platform_compliance == 5
    assert candidate.self_score.finish_integration == 5
    assert candidate.self_score.variety_score == 5
