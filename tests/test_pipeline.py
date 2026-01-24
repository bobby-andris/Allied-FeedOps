# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch
from feedops.models import ParentSKU, Variant, Candidate, Claim, Score
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.validators import validate_candidate_content
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_report, generate_patch_preview
from feedops.providers.base import LLMProvider, ImageInput
from feedops.pipeline.optimize import estimate_llm_cost


@pytest.fixture
def sample_parent_sku():
    """Create sample ParentSKU for testing."""
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
        current_description="This stylish towel bar...",
        material="Brass",
        mounting_type="Wall mount",
        weight_capacity=10.0,
        variants=[variant],
    )


# Task 5.1: Evidence Table Tests
def test_build_evidence_table_includes_parent_fields(sample_parent_sku):
    """Evidence table includes ParentSKU fields."""
    evidence = build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "master_sku" in fields
    assert "category" in fields
    assert "material" in fields


def test_format_evidence_markdown_creates_table(sample_parent_sku):
    """format_evidence_markdown creates valid markdown table."""
    evidence = build_evidence_table(sample_parent_sku)
    markdown = format_evidence_markdown(evidence)
    assert "| Attribute | Value | Source |" in markdown
    assert "Towel Bars" in markdown
    assert "Brass" in markdown


def test_format_evidence_markdown_does_not_truncate(sample_parent_sku):
    """format_evidence_markdown preserves full values."""
    long_value = "X" * 90 + "TAIL"
    sample_parent_sku.current_description = long_value
    evidence = build_evidence_table(sample_parent_sku)
    markdown = format_evidence_markdown(evidence)
    assert "TAIL" in markdown


def test_build_evidence_table_includes_image_url(sample_parent_sku):
    """Evidence table includes main image URL when available."""
    evidence = build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "main_image_url" in fields


def test_build_evidence_table_includes_high_performing_keywords(sample_parent_sku, monkeypatch):
    """Evidence table includes high-performing keywords when available."""
    from feedops.pipeline import evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "fetch_high_performing_keywords",
        lambda category: ["wall mount towel bar", "bath towel holder"],
    )
    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "high_performing_keywords" in fields


def test_build_evidence_table_includes_external_keywords(sample_parent_sku, monkeypatch):
    """Evidence table includes external keyword bank phrases when available."""
    from feedops.pipeline import evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "get_external_keywords",
        lambda category: ["bath towel rack", "towel rail"],
    )
    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "external_keywords" in fields


# Task 5.2: Claim Verifier Tests
def test_verify_claims_marks_valid_claims(sample_parent_sku):
    """Valid claims are marked as verified."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[
            Claim(claim="made of Brass", source_field="material", source_value="Brass"),
            Claim(claim="wall mounted", source_field="mounting_type", source_value="Wall mount"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, sample_parent_sku)
    assert verified.claims[0].verified is True
    assert verified.claims[1].verified is True
    assert len(errors) == 0


def test_verify_claims_rejects_invalid_claims(sample_parent_sku):
    """Invalid claims are marked as rejected with reason."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[
            Claim(claim="made of Steel", source_field="material", source_value="Steel"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, sample_parent_sku)
    assert verified.claims[0].verified is False
    assert "Steel" in verified.claims[0].rejection_reason
    assert len(errors) == 1


def test_verify_claims_requires_exact_material_match(sample_parent_sku):
    """Material claims must exactly match source value."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[
            Claim(claim="solid brass construction", source_field="material", source_value="Solid Brass"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, sample_parent_sku)
    assert verified.claims[0].verified is False
    assert errors


def test_verify_claims_accepts_numeric_units_and_trailing_decimals(sample_parent_sku):
    """Numeric claims should verify even if source_value adds units or drops trailing .0."""
    parent = ParentSKU(
        master_sku=sample_parent_sku.master_sku,
        category=sample_parent_sku.category,
        collection=sample_parent_sku.collection,
        current_title=sample_parent_sku.current_title,
        current_description=sample_parent_sku.current_description,
        material=sample_parent_sku.material,
        mounting_type=sample_parent_sku.mounting_type,
        center_to_center=18.0,
        weight_capacity=10.0,
        variants=sample_parent_sku.variants,
    )
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[
            Claim(claim="18-inch center-to-center", source_field="center_to_center", source_value="18 in"),
            Claim(claim="Weight capacity is 10 lb", source_field="weight_capacity", source_value="10 lb"),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    verified, errors = verify_claims(candidate, parent)
    assert verified.claims[0].verified is True
    assert verified.claims[1].verified is True
    assert errors == []


# Task 5.2b: Candidate Content Validation Tests
def test_validate_candidate_content_rejects_catalog_csv_references():
    """Candidate content with catalog_csv references is rejected."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 20 + "(catalog_csv.Material)",
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    errors = validate_candidate_content(candidate)
    assert errors
    assert any("catalog_csv" in error for error in errors)


# Task 5.3: Candidate Generator Tests
def test_build_prompt_includes_evidence(sample_parent_sku):
    """build_prompt includes evidence table."""
    prompt = build_prompt(sample_parent_sku)
    assert "Available Product Data" in prompt
    assert "Towel Bars" in prompt
    assert "Brass" in prompt


def test_build_prompt_includes_constraints(sample_parent_sku):
    """build_prompt includes character constraints."""
    prompt = build_prompt(sample_parent_sku)
    assert "150" in prompt  # max title length
    assert "500" in prompt  # min description length


def test_build_prompt_includes_prompt_overhaul_rules(sample_parent_sku):
    """build_prompt includes new prompt rules and platform guidance."""
    prompt = build_prompt(sample_parent_sku)
    assert "No source citations in customer-facing fields" in prompt
    assert "catalog_csv" in prompt
    assert "Titles/descriptions must be citation-free" in prompt
    assert "Only the claims array may include source attribution" in prompt
    assert "If an image is provided" in prompt
    assert "confirm material, finish, color, and visible features" in prompt
    assert "Allied Brass is a niche brand" in prompt
    assert "brand at the end" in prompt
    assert "Brand must be last" in prompt
    assert "No internal SKU codes" in prompt
    assert "natural query language" in prompt
    assert "external_keywords" in prompt
    assert "keyword phrases only" in prompt.lower()
    assert "Title zones" in prompt
    assert "1-30" in prompt
    assert "31-70" in prompt
    assert "Title and description are equally important outputs" in prompt
    assert "Google Shopping / Performance Max" in prompt
    assert "seed prompt" in prompt
    assert "Microsoft / Bing Shopping" in prompt
    assert "Copilot confidence" in prompt
    assert "Shopify (On-Site)" in prompt
    assert "Output fields (must map to schema)" in prompt
    assert "google_short_title" in prompt
    assert "omit brand" in prompt.lower()
    assert "google_title" in prompt
    assert "google_description" in prompt
    assert "bing_title" in prompt
    assert "bing_description" in prompt
    assert "shopify_title" in prompt
    assert "shopify_description" in prompt


def test_candidate_schema_has_required_fields():
    """Schema includes platform fields, claims, self_score."""
    assert "google_title" in str(CANDIDATE_SCHEMA)
    assert "google_short_title" in str(CANDIDATE_SCHEMA)
    assert "google_description" in str(CANDIDATE_SCHEMA)
    assert "bing_title" in str(CANDIDATE_SCHEMA)
    assert "bing_description" in str(CANDIDATE_SCHEMA)
    assert "shopify_title" in str(CANDIDATE_SCHEMA)
    assert "shopify_description" in str(CANDIDATE_SCHEMA)
    assert "claims" in str(CANDIDATE_SCHEMA)
    assert "self_score" in str(CANDIDATE_SCHEMA)


@pytest.mark.asyncio
async def test_generate_candidate_fetches_image_and_passes_to_provider(sample_parent_sku):
    """generate_candidate fetches image and passes it to provider."""
    sample_parent_sku.variants[0].main_image_url = "https://example.com/image.png"
    image_input = ImageInput(
        data=b"image-bytes",
        mime_type="image/png",
        source_url="https://example.com/image.png",
    )
    llm = AsyncMock(spec=LLMProvider)
    llm.generate.return_value = {
        "google_title": "Test Google Title",
        "google_short_title": "Test Short Title",
        "google_description": "Test description " * 30,
        "bing_title": "Test Bing Title",
        "bing_description": "Test description " * 30,
        "shopify_title": "Test Shopify Title",
        "shopify_description": "<p>Test description</p>",
        "claims": [],
        "self_score": {
            "specificity": 5,
            "benefit_coverage": 5,
            "keyword_inclusion": 5,
            "format_adherence": 5,
            "brand_voice": 5,
            "factual_accuracy": 5,
        },
    }

    with patch("feedops.pipeline.generator.fetch_image", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = image_input
        candidate = await generate_candidate(sample_parent_sku, llm)
        mock_fetch.assert_awaited_once_with("https://example.com/image.png")
        assert candidate.google_title == "Test Google Title"
        _, kwargs = llm.generate.call_args
        assert kwargs["image"] == image_input


@pytest.mark.asyncio
async def test_generate_candidate_skips_image_when_missing(sample_parent_sku):
    """generate_candidate skips image fetch when URL missing."""
    sample_parent_sku.variants[0].main_image_url = None
    llm = AsyncMock(spec=LLMProvider)
    llm.generate.return_value = {
        "google_title": "Test Google Title",
        "google_short_title": "Test Short Title",
        "google_description": "Test description " * 30,
        "bing_title": "Test Bing Title",
        "bing_description": "Test description " * 30,
        "shopify_title": "Test Shopify Title",
        "shopify_description": "<p>Test description</p>",
        "claims": [],
        "self_score": {
            "specificity": 5,
            "benefit_coverage": 5,
            "keyword_inclusion": 5,
            "format_adherence": 5,
            "brand_voice": 5,
            "factual_accuracy": 5,
        },
    }

    with patch("feedops.pipeline.generator.fetch_image", new_callable=AsyncMock) as mock_fetch:
        candidate = await generate_candidate(sample_parent_sku, llm)
        mock_fetch.assert_not_awaited()
        assert candidate.google_title == "Test Google Title"
        _, kwargs = llm.generate.call_args
        assert kwargs.get("image") is None


# Task 5.4: Report Generator Tests
def test_generate_report_includes_scores(sample_parent_sku):
    """Report includes quality scores."""
    candidate = Candidate(
        google_title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        google_short_title="18-Inch Towel Bar",
        google_description="Crafted from solid brass " * 20,
        bing_title="Allied Brass 18-Inch Towel Bar (Towel Holder) | Solid Brass",
        bing_description="Crafted from solid brass " * 20,
        shopify_title="18-Inch Towel Bar | Allied Brass",
        shopify_description="<p>Crafted from solid brass</p>",
        claims=[
            Claim(claim="solid brass", source_field="material", source_value="Brass", verified=True),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    report = generate_report(sample_parent_sku, candidate, [])
    assert "Quality Score" in report or "Composite" in report
    assert "80" in report  # 80% composite


def test_generate_report_includes_llm_input_details(sample_parent_sku):
    """Report includes LLM input metadata, evidence, and prompt."""
    candidate = Candidate(
        google_title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        google_short_title="18-Inch Towel Bar",
        google_description="Crafted from solid brass " * 20,
        bing_title="Allied Brass 18-Inch Towel Bar (Towel Holder) | Solid Brass",
        bing_description="Crafted from solid brass " * 20,
        shopify_title="18-Inch Towel Bar | Allied Brass",
        shopify_description="<p>Crafted from solid brass</p>",
        claims=[
            Claim(claim="solid brass", source_field="material", source_value="Brass", verified=True),
        ],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    evidence_table = "\n".join([
        "## Available Product Data",
        "",
        "| Attribute | Value | Source |",
        "|-----------|-------|--------|",
        "| material | Brass | material |",
    ])
    prompt = "FULL PROMPT TEXT"

    report = generate_report(
        sample_parent_sku,
        candidate,
        [],
        evidence_table=evidence_table,
        prompt=prompt,
        image_url="https://example.com/image.jpg",
        provider_name="openai/gpt-5.2",
        token_usage={"prompt_tokens": 1200, "completion_tokens": 300},
        estimated_cost=0.01,
    )

    assert "Input Data Sent to LLM" in report
    assert "Provider/Model" in report
    assert "openai/gpt-5.2" in report
    assert "https://example.com/image.jpg" in report
    assert evidence_table in report
    assert "<details>" in report
    assert prompt in report
    assert "Prompt tokens: 1200" in report
    assert "Completion tokens: 300" in report
    assert "Estimated Cost" in report


def test_estimate_llm_cost_ignores_non_dict_usage():
    """estimate_llm_cost returns None for non-dict token usage."""
    class Dummy:
        pass

    assert estimate_llm_cost("openai/gpt-5.2", Dummy()) is None


def test_generate_google_patch_preview_structure(sample_parent_sku):
    """Google patch preview has required Merchant Center fields."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate, platform="google")
    assert "offerId" in patch
    assert "title" in patch
    assert "description" in patch


def test_generate_bing_patch_preview_structure(sample_parent_sku):
    """Bing patch preview includes platform fields."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate, platform="bing")
    assert "sku" in patch
    assert "title" in patch
    assert "description" in patch


def test_generate_shopify_patch_preview_structure(sample_parent_sku):
    """Shopify patch preview includes platform fields."""
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate, platform="shopify")
    assert "productId" in patch
    assert "title" in patch
    assert "body_html" in patch
