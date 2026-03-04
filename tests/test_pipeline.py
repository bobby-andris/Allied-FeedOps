# tests/test_pipeline.py
from unittest.mock import AsyncMock, patch

import pytest

from feedops.models import Candidate, Claim, ParentSKU, Score, Variant
from feedops.pipeline import generator as generator_module
from feedops.pipeline.claim_extraction import extract_claims
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.generator import (
    build_prompt,
    build_split_prompt,
    generate_candidate,
    generate_candidates,
    parse_candidate_response,
)
from feedops.pipeline.optimize import estimate_llm_cost
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_patch_preview, generate_report
from feedops.pipeline.selection import RankedCandidate
from feedops.pipeline.validators import validate_candidate_content
from feedops.pipeline.verifier import verify_claims
from feedops.providers.base import ImageInput, LLMProvider
from feedops.quality.scoring import CandidateHeuristicScore, HeuristicScore


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


@pytest.mark.asyncio
async def test_optimize_parent_sku_reports_product_not_found(tmp_path):
    from feedops.pipeline.optimize import optimize_parent_sku

    with pytest.raises(ValueError, match="Product not found"):
        await optimize_parent_sku(
            master_sku="MISSING-SKU",
            catalog_path="samples/sample-catalog.csv",
            dry_run=True,
            output_dir=tmp_path,
            exports_dir=tmp_path,
            num_candidates=1,
        )


@pytest.mark.asyncio
async def test_optimize_parent_sku_reports_api_unavailable(tmp_path, monkeypatch):
    from feedops.loaders import unified_loader
    from feedops.pipeline.optimize import optimize_parent_sku

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "empty.db"))

    def _raise_api(*_args, **_kwargs):
        raise RuntimeError("API down")

    monkeypatch.setattr(unified_loader, "fetch_shopify_product", _raise_api)

    with pytest.raises(ValueError, match="API unavailable"):
        await optimize_parent_sku(
            master_sku="TD-22",
            catalog_path="does/not/exist.csv",
            dry_run=True,
            output_dir=tmp_path,
            exports_dir=tmp_path,
            num_candidates=1,
        )


@pytest.mark.asyncio
async def test_optimize_parent_sku_passes_force_refresh(tmp_path, monkeypatch):
    from feedops.loaders.unified_loader import UnifiedLoadStatus
    from feedops.pipeline import optimize as optimize_module

    calls = {}

    def _fake_loader(*_args, **kwargs):
        calls["force_refresh"] = kwargs.get("force_refresh")
        return None, UnifiedLoadStatus(csv_attempted=True)

    monkeypatch.setattr(
        optimize_module,
        "load_parent_sku_unified_with_status",
        _fake_loader,
    )

    with pytest.raises(ValueError, match="Product not found"):
        await optimize_module.optimize_parent_sku(
            master_sku="MISSING-SKU",
            catalog_path="samples/sample-catalog.csv",
            dry_run=True,
            output_dir=tmp_path,
            exports_dir=tmp_path,
            num_candidates=1,
            force_refresh=True,
        )

    assert calls["force_refresh"] is True


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


def test_build_evidence_table_includes_high_performing_keywords(
    sample_parent_sku, monkeypatch
):
    """Evidence table includes MasterSKU-level keyword intent when available."""
    from feedops.pipeline import evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "fetch_master_sku_keywords",
        lambda item_group_id, item_ids, category=None: [
            "wall mount towel bar",
            "bath towel holder",
        ],
    )
    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "keyword_intent_master" in fields


def test_build_evidence_table_includes_external_keywords(
    sample_parent_sku, monkeypatch
):
    """Evidence table includes external keyword bank phrases when available."""
    from feedops.pipeline import evidence as evidence_module

    monkeypatch.setattr(
        evidence_module,
        "get_external_keywords",
        lambda category=None, master_sku=None: ["bath towel rack", "towel rail"],
    )
    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    fields = {e.field for e in evidence}
    assert "external_keywords" in fields


def test_build_evidence_table_excludes_finish_specific_keywords(
    sample_parent_sku, monkeypatch
):
    """Finish-specific keywords are excluded from MasterSKU-level keyword intent."""
    from feedops.pipeline import evidence as evidence_module

    # Ensure the ParentSKU represents multiple finish variants (MasterSKU-level group).
    sample_parent_sku.variants.append(
        Variant(
            option_sku="1031/18-SN",
            finish="Satin Nickel",
            finish_code="SN",
            gmc_id="shopify_US_4542872518788_99999999999999",
            position=2,
        )
    )

    # Sample has finishes including "Antique Brass" and "Satin Nickel", and material "Brass".
    monkeypatch.setattr(
        evidence_module,
        "fetch_master_sku_keywords",
        lambda item_group_id, item_ids, category=None: [
            "wall mount towel bar",
            "antique brass towel bar",
            "satin nickel towel bar",
            "brass towel bar",  # material-level, should remain
        ],
    )
    # No external keywords for this test; keep focus on finish filtering.
    monkeypatch.setattr(
        evidence_module,
        "get_external_keywords",
        lambda category=None, master_sku=None: [],
    )

    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    kw_row = next(e for e in evidence if e.field == "keyword_intent_master")
    assert "wall mount towel bar" in kw_row.value
    assert "brass towel bar" in kw_row.value
    assert "antique brass" not in kw_row.value.lower()
    assert "satin nickel" not in kw_row.value.lower()


def test_build_evidence_table_keyword_gaps_are_category_relevant_and_finish_excluded(
    sample_parent_sku, monkeypatch
):
    """Keyword gap evidence keeps category-relevant gaps and excludes finish-specific terms."""
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
        lambda master_sku, **kwargs: [
            {"query_text": "bathroom towel bar wall mount", "avg_monthly_searches": 2400},
            {"query_text": "antique brass towel bar", "avg_monthly_searches": 2100},
            {"query_text": "kitchen faucet pull down", "avg_monthly_searches": 3000},
        ],
    )
    monkeypatch.setattr(
        evidence_module,
        "format_search_queries_for_evidence",
        lambda queries, context, **kwargs: [],
    )

    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    row = next(e for e in evidence if e.field == "keyword_gaps_current_title")
    value_lower = row.value.lower()

    assert "bathroom towel bar wall mount" in value_lower
    assert "antique brass towel bar" not in value_lower
    assert "kitchen faucet pull down" not in value_lower


def test_build_evidence_table_competitor_rows_filter_speculative_language(
    sample_parent_sku, monkeypatch
):
    """Competitor evidence rows must not carry speculative 'better than' language."""
    from feedops.pipeline import competitor_evidence as competitor_module
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
        lambda master_sku: [],
    )
    monkeypatch.setattr(
        evidence_module,
        "format_search_queries_for_evidence",
        lambda queries, context: [],
    )

    fake_competitor = competitor_module.CompetitorEvidence(
        category="Towel Bars",
        direct=competitor_module.CompetitorBucket(
            listing_count=2,
            top_domains=(competitor_module.NameCount(name="build.com", count=2),),
            top_brands=(competitor_module.NameCount(name="Delta", count=1),),
            patterns=(
                competitor_module.CompetitorPattern(
                    pattern_type="keyword",
                    pattern_value="better than competitors",
                    frequency=10,
                    avg_position=2.2,
                    sources=("build.com",),
                    example_titles=("Better than competitors towel bar",),
                ),
                competitor_module.CompetitorPattern(
                    pattern_type="keyword",
                    pattern_value="wall mount towel bar",
                    frequency=9,
                    avg_position=2.8,
                    sources=("build.com",),
                    example_titles=("Wall Mount Towel Bar",),
                ),
            ),
        ),
        marketplace=competitor_module.CompetitorBucket(0, (), (), ()),
        mixed=competitor_module.CompetitorBucket(0, (), (), ()),
        unknown=competitor_module.CompetitorBucket(0, (), (), ()),
    )
    monkeypatch.setattr(
        competitor_module,
        "build_competitor_evidence",
        lambda *args, **kwargs: fake_competitor,
    )

    evidence = evidence_module.build_evidence_table(sample_parent_sku)
    comp_rows = [e for e in evidence if e.source.startswith("competitor_evidence")]

    assert comp_rows
    combined = " ".join(row.value.lower() for row in comp_rows)
    assert "wall mount towel bar" in combined
    assert "better than" not in combined
    assert "superior" not in combined
    assert "not found in competitors" not in combined


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
            Claim(
                claim="wall mounted",
                source_field="mounting_type",
                source_value="Wall mount",
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
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
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
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
            Claim(
                claim="solid brass construction",
                source_field="material",
                source_value="Solid Brass",
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
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
            Claim(
                claim="18-inch center-to-center",
                source_field="center_to_center",
                source_value="18 in",
            ),
            Claim(
                claim="Weight capacity is 10 lb",
                source_field="weight_capacity",
                source_value="10 lb",
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    verified, errors = verify_claims(candidate, parent)
    assert verified.claims[0].verified is True
    assert verified.claims[1].verified is True
    assert errors == []


# Task 5.2a: Auto-extracted claim verification tests
def test_verify_claims_auto_extracts_finish_capacity_dimension(sample_parent_sku):
    """Auto-extraction should detect finish, capacity, and dimensions from text."""
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
        google_title="18-inch center-to-center towel bar in Antique Brass supports up to 10 lb",
        google_short_title="18-inch towel bar",
        google_description="Test description.",
        bing_title="Test Bing Title",
        bing_description="Test description.",
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    verified, errors = verify_claims(candidate, parent)
    fields = {c.source_field for c in verified.claims}
    assert "available_finishes" in fields
    assert "center_to_center" in fields
    assert "weight_capacity" in fields
    assert errors == []


def test_verify_claims_auto_extracts_material_literal_mismatch(sample_parent_sku):
    """Auto-extracted material claims must be verified exactly."""
    parent = ParentSKU(
        master_sku=sample_parent_sku.master_sku,
        category=sample_parent_sku.category,
        collection=sample_parent_sku.collection,
        current_title=sample_parent_sku.current_title,
        current_description=sample_parent_sku.current_description,
        material="Brass",
        variants=sample_parent_sku.variants,
    )
    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Solid brass construction for lasting durability.",
        bing_title="Test Bing Title",
        bing_description="Test description.",
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    verified, errors = verify_claims(candidate, parent)
    material_claims = [c for c in verified.claims if c.source_field == "material"]
    assert material_claims
    assert any(not c.verified for c in material_claims)
    assert errors


def test_verify_claims_dedupes_auto_extracted_dimensions(sample_parent_sku):
    """Duplicate dimension mentions should collapse into a single claim."""
    parent = ParentSKU(
        master_sku=sample_parent_sku.master_sku,
        category=sample_parent_sku.category,
        collection=sample_parent_sku.collection,
        current_title=sample_parent_sku.current_title,
        current_description=sample_parent_sku.current_description,
        center_to_center=18.0,
        variants=sample_parent_sku.variants,
    )
    candidate = Candidate(
        google_title="18-inch center-to-center towel bar",
        google_short_title="18-inch towel bar",
        google_description="Test description.",
        bing_title="18-inch center-to-center towel bar",
        bing_description="Test description.",
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    verified, _ = verify_claims(candidate, parent)
    dimension_claims = [
        c for c in verified.claims if c.source_field == "center_to_center"
    ]
    assert len(dimension_claims) == 1


# Fix 2.2: Durability claim extraction tests
def test_extract_durability_claims_verified_for_brass(sample_parent_sku):
    """Durability claims are verified when material is brass."""
    candidate = Candidate(
        google_title="Corrosion-Resistant Towel Bar | Allied Brass",
        google_short_title="Towel Bar",
        google_description="This rust-free and tarnish-resistant towel bar is built to last.",
        bing_title="Corrosion-Resistant Towel Bar | Allied Brass",
        bing_description="This rust-free and tarnish-resistant towel bar is built to last.",
        shopify_title="Corrosion-Resistant Towel Bar | Allied Brass",
        shopify_description="<p>This rust-free and tarnish-resistant towel bar is built to last.</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    claims = extract_claims(candidate, sample_parent_sku)
    # Durability claims use source_field like "corrosion_resistance", "rust_resistance", etc.
    durability_fields = {
        "corrosion_resistance",
        "rust_resistance",
        "tarnish_resistance",
        "water_resistance",
    }
    durability_claims = [c for c in claims if c.source_field in durability_fields]
    assert len(durability_claims) >= 1
    # Should not have UNVERIFIED prefix since material is Brass
    assert not any("UNVERIFIED" in c.claim for c in durability_claims)


def test_extract_durability_claims_unverified_for_other_materials():
    """Durability claims are marked unverified for non-brass/steel materials."""
    variant = Variant(
        option_sku="TEST-1",
        finish="Chrome",
        finish_code="CH",
        gmc_id="test_gmc",
        position=1,
    )
    parent = ParentSKU(
        master_sku="TEST",
        category="Towel Bars",
        current_title="Test Towel Bar",
        current_description="Test description",
        material="Aluminum",  # Not brass or stainless steel
        variants=[variant],
    )
    candidate = Candidate(
        google_title="Corrosion-Free Towel Bar",
        google_short_title="Towel Bar",
        google_description="This rust-free towel bar is built to last.",
        bing_title="Corrosion-Free Towel Bar",
        bing_description="This rust-free towel bar is built to last.",
        shopify_title="Corrosion-Free Towel Bar",
        shopify_description="<p>This rust-free towel bar is built to last.</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    claims = extract_claims(candidate, parent)
    # Durability claims use source_field like "corrosion_resistance", "rust_resistance", etc.
    durability_fields = {
        "corrosion_resistance",
        "rust_resistance",
        "tarnish_resistance",
        "water_resistance",
    }
    durability_claims = [c for c in claims if c.source_field in durability_fields]
    assert len(durability_claims) >= 1
    # Should have UNVERIFIED prefix since material is Aluminum
    assert any("UNVERIFIED" in c.claim for c in durability_claims)


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
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    errors = validate_candidate_content(candidate)
    assert errors
    assert any("catalog_csv" in error for error in errors)


def test_validate_candidate_content_rejects_speculative_competitive_claims():
    """Speculative competitive claims are blocked unless phrased as evidence-backed facts."""
    candidate = Candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass - Allied Brass",
        google_short_title="18-Inch Towel Bar",
        google_description=(
            "This towel bar is better than competitors and offers superior quality for any bathroom."
        ),
        bing_title="18-Inch Wall Mount Towel Bar Solid Brass - Allied Brass",
        bing_description="Distinctive design not found in competitors.",
        shopify_title="18-Inch Wall Mount Towel Bar Solid Brass",
        shopify_description="<p>Set this apart from competitors with stronger design.</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    errors = validate_candidate_content(candidate)
    assert any("speculative competitive claim" in error for error in errors)


def test_validate_candidate_content_allows_evidence_style_comparison_language():
    """Evidence-style material comparisons remain allowed."""
    candidate = Candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass - Allied Brass",
        google_short_title="18-Inch Towel Bar",
        google_description=(
            "Solid brass construction with concealed mounting hardware for daily use."
        ),
        bing_title="18-Inch Wall Mount Towel Bar Solid Brass - Allied Brass",
        bing_description=(
            "Solid brass construction compared with common die-cast zinc alternatives."
        ),
        shopify_title="18-Inch Wall Mount Towel Bar Solid Brass",
        shopify_description="<p>Solid brass build for lasting bathroom performance.</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    errors = validate_candidate_content(candidate)
    assert not any("speculative competitive claim" in error for error in errors)


# Task 5.3: Candidate Generator Tests
def test_build_prompt_includes_evidence(sample_parent_sku):
    """build_prompt includes evidence table."""
    prompt = build_prompt(sample_parent_sku)
    assert "Available Product Data" in prompt
    assert "Towel Bars" in prompt
    assert "Brass" in prompt


def test_build_prompt_uses_canonical_prompt_loader(sample_parent_sku, monkeypatch):
    """build_prompt uses prompt_loader.get_system_prompt() for the system prompt."""
    sentinel_prompt = "SENTINEL_CANONICAL_PROMPT"
    monkeypatch.setattr(generator_module, "get_system_prompt", lambda: sentinel_prompt)

    prompt = build_prompt(sample_parent_sku)
    assert sentinel_prompt in prompt


def test_build_split_prompt_uses_canonical_prompt_loader(sample_parent_sku, monkeypatch):
    """build_split_prompt returns system prompt from prompt_loader.get_system_prompt()."""
    sentinel_prompt = "SPLIT_PROMPT_SENTINEL"
    monkeypatch.setattr(generator_module, "get_system_prompt", lambda: sentinel_prompt)

    system_prompt, _ = build_split_prompt(sample_parent_sku)
    assert system_prompt == sentinel_prompt


def test_build_split_prompt_includes_gold_examples_when_available(sample_parent_sku, monkeypatch):
    monkeypatch.setattr(
        generator_module,
        "format_gold_standard_examples_bundle",
        lambda max_examples=2: "GOLD_EXAMPLES_SENTINEL",
    )

    _, user_prompt = build_split_prompt(sample_parent_sku)
    assert "## Gold Standard Examples" in user_prompt
    assert "GOLD_EXAMPLES_SENTINEL" in user_prompt


def test_build_split_prompt_omits_gold_examples_when_unavailable(sample_parent_sku, monkeypatch):
    monkeypatch.setattr(
        generator_module,
        "format_gold_standard_examples_bundle",
        lambda max_examples=2: "",
    )

    _, user_prompt = build_split_prompt(sample_parent_sku)
    assert "Gold Standard Examples" not in user_prompt


def test_candidate_schema_has_required_fields():
    """Schema includes platform fields, claims, and self_score."""
    assert "google_title" in str(CANDIDATE_SCHEMA)
    assert "google_short_title" in str(CANDIDATE_SCHEMA)
    assert "google_description" in str(CANDIDATE_SCHEMA)
    assert "bing_title" in str(CANDIDATE_SCHEMA)
    assert "bing_description" in str(CANDIDATE_SCHEMA)
    assert "shopify_title" in str(CANDIDATE_SCHEMA)
    assert "shopify_description" in str(CANDIDATE_SCHEMA)
    assert "claims" in str(CANDIDATE_SCHEMA)


def test_parse_candidate_response_trims_google_short_title():
    """Long google_short_title is trimmed to pass validation."""
    long_short_title = (
        "Assorted Wall Accessories 22.5-Inch Solid Brass with Concealed Mounting | "
        "Allied Brass"
    )
    assert len(long_short_title) > 70

    response = {
        "google_title": "Wall Accessory 22.5-Inch Solid Brass | Allied Brass",
        "google_short_title": long_short_title,
        "google_description": "Test description " * 30,
        "bing_title": "Wall Accessory 22.5-Inch Solid Brass | Allied Brass",
        "bing_description": "Test description " * 30,
        "shopify_title": "Wall Accessory 22.5-Inch Solid Brass | Allied Brass",
        "shopify_description": "<p>Test description</p>",
        "claims": [],
        "self_score": {
            "hook_quality": 5,
            "product_specificity": 5,
            "competitive_diff": 5,
            "keyword_integration": 5,
            "customer_scenario": 5,
            "emotional_resonance": 5,
            "factual_accuracy": 5,
            "platform_compliance": 5,
            "finish_integration": 5,
            "variety_score": 5,
        },
    }

    candidate = parse_candidate_response(response)
    assert len(candidate.google_short_title) <= 70


@pytest.mark.asyncio
async def test_generate_candidate_fetches_image_and_passes_to_provider(
    sample_parent_sku,
):
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
            "hook_quality": 5,
            "product_specificity": 5,
            "competitive_diff": 5,
            "keyword_integration": 5,
            "customer_scenario": 5,
            "emotional_resonance": 5,
            "factual_accuracy": 5,
            "platform_compliance": 5,
            "finish_integration": 5,
            "variety_score": 5,
        },
    }

    with patch(
        "feedops.pipeline.generator.fetch_image", new_callable=AsyncMock
    ) as mock_fetch:
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
            "hook_quality": 5,
            "product_specificity": 5,
            "competitive_diff": 5,
            "keyword_integration": 5,
            "customer_scenario": 5,
            "emotional_resonance": 5,
            "factual_accuracy": 5,
            "platform_compliance": 5,
            "finish_integration": 5,
            "variety_score": 5,
        },
    }

    with patch(
        "feedops.pipeline.generator.fetch_image", new_callable=AsyncMock
    ) as mock_fetch:
        candidate = await generate_candidate(sample_parent_sku, llm)
        mock_fetch.assert_not_awaited()
        assert candidate.google_title == "Test Google Title"
        _, kwargs = llm.generate.call_args
        assert kwargs.get("image") is None


@pytest.mark.asyncio
async def test_generate_candidates_fetches_image_once_and_generates_n(
    sample_parent_sku,
):
    """generate_candidates fetches image once and returns all candidates."""
    sample_parent_sku.variants[0].main_image_url = "https://example.com/image.png"
    image_input = ImageInput(
        data=b"image-bytes",
        mime_type="image/png",
        source_url="https://example.com/image.png",
    )
    llm = AsyncMock(spec=LLMProvider)
    _default_score = {
        "hook_quality": 5,
        "product_specificity": 5,
        "competitive_diff": 5,
        "keyword_integration": 5,
        "customer_scenario": 5,
        "emotional_resonance": 5,
        "factual_accuracy": 5,
        "platform_compliance": 5,
        "finish_integration": 5,
        "variety_score": 5,
    }
    llm.generate.side_effect = [
        {
            "google_title": "18-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "google_short_title": "Test Short Title 1",
            "google_description": "Test description " * 30,
            "bing_title": "18-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "bing_description": "Test description " * 30,
            "shopify_title": "Test Shopify Title 1",
            "shopify_description": "<p>Test description</p>",
            "claims": [],
            "self_score": _default_score,
        },
        {
            "google_title": "24-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "google_short_title": "Test Short Title 2",
            "google_description": "Test description " * 30,
            "bing_title": "24-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "bing_description": "Test description " * 30,
            "shopify_title": "Test Shopify Title 2",
            "shopify_description": "<p>Test description</p>",
            "claims": [],
            "self_score": _default_score,
        },
        {
            "google_title": "30-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "google_short_title": "Test Short Title 3",
            "google_description": "Test description " * 30,
            "bing_title": "30-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "bing_description": "Test description " * 30,
            "shopify_title": "Test Shopify Title 3",
            "shopify_description": "<p>Test description</p>",
            "claims": [],
            "self_score": _default_score,
        },
    ]

    with patch(
        "feedops.pipeline.generator.fetch_image", new_callable=AsyncMock
    ) as mock_fetch, patch(
        "feedops.pipeline.generator._needs_keyword_alignment_retry",
        return_value=[],
    ):
        mock_fetch.return_value = image_input
        candidates, errors = await generate_candidates(sample_parent_sku, llm, 3)

    mock_fetch.assert_awaited_once_with("https://example.com/image.png")
    assert llm.generate.call_count == 3
    assert errors == []
    assert [c.candidate_index for c in candidates] == [0, 1, 2]
    assert all(c.num_candidates == 3 for c in candidates)


@pytest.mark.asyncio
async def test_generate_candidates_skips_failed_attempts(sample_parent_sku):
    """generate_candidates skips invalid responses and continues."""
    sample_parent_sku.variants[0].main_image_url = None
    llm = AsyncMock(spec=LLMProvider)
    _default_score = {
        "hook_quality": 5,
        "product_specificity": 5,
        "competitive_diff": 5,
        "keyword_integration": 5,
        "customer_scenario": 5,
        "emotional_resonance": 5,
        "factual_accuracy": 5,
        "platform_compliance": 5,
        "finish_integration": 5,
        "variety_score": 5,
    }
    llm.generate.side_effect = [
        {
            "google_short_title": "Test Short Title",
            "google_description": "Test description " * 30,
            "bing_title": "Test Bing Title",
            "bing_description": "Test description " * 30,
            "shopify_title": "Test Shopify Title",
            "shopify_description": "<p>Test description</p>",
            "claims": [],
            "self_score": _default_score,
        },
        {
            "google_title": "24-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "google_short_title": "Test Short Title 2",
            "google_description": "Test description " * 30,
            "bing_title": "24-Inch Towel Bar, Skyline Collection, Solid Brass, Allied Brass",
            "bing_description": "Test description " * 30,
            "shopify_title": "Test Shopify Title 2",
            "shopify_description": "<p>Test description</p>",
            "claims": [],
            "self_score": _default_score,
        },
    ]

    with patch(
        "feedops.pipeline.generator._needs_keyword_alignment_retry",
        return_value=[],
    ):
        candidates, errors = await generate_candidates(sample_parent_sku, llm, 2)

    assert len(candidates) == 1
    # Title normalization reorders: collection moves before "Allied Brass" brand segment
    assert candidates[0].google_title == "24-Inch Towel Bar, Solid Brass, Skyline Collection, Allied Brass"
    assert len(errors) == 1


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
            Claim(
                claim="solid brass",
                source_field="material",
                source_value="Brass",
                verified=True,
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
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
            Claim(
                claim="solid brass",
                source_field="material",
                source_value="Brass",
                verified=True,
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    evidence_table = "\n".join(
        [
            "## Available Product Data",
            "",
            "| Attribute | Value | Source |",
            "|-----------|-------|--------|",
            "| material | Brass | material |",
        ]
    )
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


def test_generate_report_includes_soft_gate_warnings(sample_parent_sku):
    candidate = Candidate(
        google_title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        google_short_title="18-Inch Towel Bar",
        google_description="Crafted from solid brass " * 20,
        bing_title="Allied Brass 18-Inch Towel Bar (Towel Holder) | Solid Brass",
        bing_description="Crafted from solid brass " * 20,
        shopify_title="18-Inch Towel Bar | Allied Brass",
        shopify_description="<p>Crafted from solid brass</p>",
        claims=[
            Claim(
                claim="solid brass",
                source_field="material",
                source_value="Brass",
                verified=True,
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    base_platform = HeuristicScore(ctr_proxy=5, cvr_proxy=5, brand_voice=5)
    heuristic = CandidateHeuristicScore(
        google=base_platform,
        bing=base_platform,
        shopify=base_platform,
        weighted_composite=75.0,
        soft_gate_penalty=2.0,
        adjusted_weighted_composite=73.0,
        soft_gate_warnings=(
            "Google: Title missing primary dimension in first 70 chars",
        ),
        soft_gate_miss_counts={"google": 1, "bing": 0, "shopify": 0},
        notes=(),
    )
    ranking = [
        RankedCandidate(
            candidate=candidate, heuristic=heuristic, validation_errors=[], index=0
        )
    ]

    report = generate_report(
        sample_parent_sku, candidate, [], selection_ranking=ranking
    )

    assert "Soft-Gate Warnings" in report
    assert "Google:" in report


def test_generate_report_includes_mc_metadata_section(sample_parent_sku):
    candidate = Candidate(
        google_title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        google_short_title="18-Inch Towel Bar",
        google_description="Crafted from solid brass " * 20,
        bing_title="Allied Brass 18-Inch Towel Bar (Towel Holder) | Solid Brass",
        bing_description="Crafted from solid brass " * 20,
        shopify_title="18-Inch Towel Bar | Allied Brass",
        shopify_description="<p>Crafted from solid brass</p>",
        claims=[
            Claim(
                claim="solid brass",
                source_field="material",
                source_value="Brass",
                verified=True,
            ),
        ],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    mc_metadata = {
        "shopify_US_4542872518788_32118222192772": {
            "offerId": "shopify_US_4542872518788_32118222192772",
            "customLabel0": "label0",
            "googleProductCategory": "Home & Garden",
            "productTypes": ["Bath"],
            "destinationStatuses": [{"destination": "Shopping", "status": "approved"}],
            "itemLevelIssues": [],
            "fetched_at": "2026-01-01T00:00:00Z",
        }
    }

    report = generate_report(
        sample_parent_sku,
        candidate,
        [],
        mc_metadata=mc_metadata,
    )

    assert "Merchant Center Metadata (diagnostic)" in report
    assert "label0" in report
    assert "Home & Garden" in report


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
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
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
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate, platform="bing")
    assert "sku" in patch
    assert "title" in patch
    assert "description" in patch


def test_generate_google_variant_preview_updates_size_when_size_is_in_option_sku(
    sample_parent_sku,
    monkeypatch,
):
    from feedops.pipeline.reporter import generate_variant_patch_preview

    monkeypatch.setenv("FEEDOPS_FINISH_FORWARD_V2", "true")
    sample_parent_sku.variants.append(
        Variant(
            option_sku="1031/36-ABR",
            finish="Antique Brass",
            finish_code="ABR",
            gmc_id="shopify_US_4542872518788_99999999999998",
            product_length=36,
            product_weight=4.0,
        )
    )
    candidate = Candidate(
        google_title="18-Inch Wall Mount Towel Bar | Skyline | Allied Brass",
        google_short_title="18-Inch Towel Bar",
        google_description=(
            "Keep towels within reach.\n\n"
            "Specs:\n"
            "Length: 18 Inch\n"
        ),
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description="<p>Test description</p>",
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )

    patch = generate_variant_patch_preview(
        sample_parent_sku,
        sample_parent_sku.variants[-1],
        candidate,
        platform="google",
    )
    assert "36-Inch" in patch["title"] or "36 Inch" in patch["title"]
    assert ("Length: 36 Inch" in patch["description"]) or ("Length: 36-Inch" in patch["description"])


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
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )
    patch = generate_patch_preview(sample_parent_sku, candidate, platform="shopify")
    assert "productId" in patch
    assert "title" in patch
    assert "body_html" in patch


def test_generate_shopify_patch_preview_multi_size_body_html_is_size_agnostic(
    sample_parent_sku,
):
    sample_parent_sku.variants.append(
        Variant(
            option_sku="1031/36-ABR",
            finish="Antique Brass",
            finish_code="ABR",
            gmc_id="shopify_US_4542872518788_99999999999998",
            product_length=36,
            product_weight=4.0,
        )
    )

    candidate = Candidate(
        google_title="Test Google Title",
        google_short_title="Test Short Title",
        google_description="Test description " * 30,
        bing_title="Test Bing Title",
        bing_description="Test description " * 30,
        shopify_title="Test Shopify Title",
        shopify_description=(
            "<p>Keep towels within reach with a wall-mounted towel bar.</p>"
            "<ul><li>Solid brass construction</li></ul>"
            "<p>Specs &amp; details:</p>"
            "<ul><li>Length: 18 Inch</li></ul>"
        ),
        claims=[],
        self_score=Score(
            hook_quality=8,
            product_specificity=8,
            competitive_diff=8,
            keyword_integration=8,
            customer_scenario=8,
            emotional_resonance=8,
            factual_accuracy=8,
            platform_compliance=8,
            finish_integration=8,
            variety_score=8,
        ),
    )

    patch = generate_patch_preview(sample_parent_sku, candidate, platform="shopify")
    assert "Length:" not in patch["body_html"]
    assert "18 Inch" in patch["body_html"]
    assert "36 Inch" in patch["body_html"]
    assert "<table" in patch["body_html"]
