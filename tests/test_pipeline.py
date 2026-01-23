# tests/test_pipeline.py
import pytest
from feedops.models import ParentSKU, Variant, Candidate, Claim, Score
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.verifier import verify_claims
from feedops.pipeline.generator import build_prompt
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_report, generate_patch_preview


@pytest.fixture
def sample_parent_sku():
    """Create sample ParentSKU for testing."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        upc="123456789",
        position=1,
        product_length=20.8,
        product_weight=2.5,
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


# Task 5.2: Claim Verifier Tests
def test_verify_claims_marks_valid_claims(sample_parent_sku):
    """Valid claims are marked as verified."""
    candidate = Candidate(
        title="Test Title",
        description="Test description " * 30,
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
        title="Test Title",
        description="Test description " * 30,
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


def test_candidate_schema_has_required_fields():
    """Schema includes title, description, claims, self_score."""
    assert "title" in str(CANDIDATE_SCHEMA)
    assert "description" in str(CANDIDATE_SCHEMA)
    assert "claims" in str(CANDIDATE_SCHEMA)
    assert "self_score" in str(CANDIDATE_SCHEMA)


# Task 5.4: Report Generator Tests
def test_generate_report_includes_scores(sample_parent_sku):
    """Report includes quality scores."""
    candidate = Candidate(
        title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        description="Crafted from solid brass " * 20,
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


def test_generate_patch_preview_structure(sample_parent_sku):
    """Patch preview has required Merchant Center fields."""
    candidate = Candidate(
        title="Test Title",
        description="Test description " * 30,
        claims=[],
        self_score=Score(
            specificity=8, benefit_coverage=8, keyword_inclusion=8,
            format_adherence=8, brand_voice=8, factual_accuracy=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate)
    assert "offerId" in patch
    assert "title" in patch
    assert "description" in patch
