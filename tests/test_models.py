# tests/test_models.py
import pytest
from feedops.models.variant import Variant, parse_gmcid
from feedops.models.parent_sku import ParentSKU
from feedops.models.claim import Claim
from feedops.models.score import Score
from feedops.models.candidate import Candidate


# Task 2.1: Variant Model Tests
def test_parse_gmcid_extracts_shopify_ids():
    """GMCID format: shopify_US_{ProductID}_{VariantID}"""
    gmc_id = "shopify_US_4542872518788_32118222192772"
    product_id, variant_id = parse_gmcid(gmc_id)
    assert product_id == "4542872518788"
    assert variant_id == "32118222192772"


def test_parse_gmcid_handles_invalid_format():
    """Invalid GMCID returns None, None."""
    product_id, variant_id = parse_gmcid("invalid_format")
    assert product_id is None
    assert variant_id is None


def test_variant_model_parses_gmcid_on_creation():
    """Variant extracts Shopify IDs from GMCID."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_1000000001_2000000001",
        upc="00000000001",
        position=1,
    )
    assert variant.shopify_product_id == "1000000001"
    assert variant.shopify_variant_id == "2000000001"


# Task 2.2: ParentSKU Model Tests
def test_parent_sku_aggregates_variants():
    """ParentSKU contains list of Variant objects."""
    variants = [
        Variant(
            option_sku="1031/18-ABR",
            finish="Antique Brass",
            finish_code="ABR",
            gmc_id="shopify_US_1000000001_2000000001",
            position=1,
        ),
        Variant(
            option_sku="1031/18-PC",
            finish="Polished Chrome",
            finish_code="PC",
            gmc_id="shopify_US_1000000001_2000000002",
            position=2,
        ),
    ]
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar...",
        material="Brass",
        variants=variants,
    )
    assert parent.master_sku == "1031/18"
    assert len(parent.variants) == 2
    assert parent.variants[0].finish_code == "ABR"


def test_parent_sku_item_group_id():
    """ParentSKU item_group_id is extracted from first variant."""
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        position=1,
    )
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Test",
        current_description="Test",
        material="Brass",
        variants=[variant],
    )
    assert parent.item_group_id == "4542872518788"


# Task 2.3: Claim Model Tests
def test_claim_model_structure():
    """Claim tracks claim text, source field, and verification status."""
    claim = Claim(
        claim="18-inch length",
        source_field="product_length",
        source_value="18.0",
        verified=True,
    )
    assert claim.claim == "18-inch length"
    assert claim.source_field == "product_length"
    assert claim.verified is True


def test_claim_defaults_to_unverified():
    """Claims are unverified by default."""
    claim = Claim(
        claim="solid brass construction",
        source_field="material",
        source_value="Brass",
    )
    assert claim.verified is False


# Task 2.4: Score Model Tests
def test_score_composite_calculation():
    """Composite = sum of all scores / 60 * 100."""
    score = Score(
        specificity=8,
        benefit_coverage=9,
        keyword_inclusion=7,
        format_adherence=10,
        brand_voice=8,
        factual_accuracy=9,
    )
    # (8+9+7+10+8+9) / 60 * 100 = 51/60 * 100 = 85%
    assert score.composite == 85.0


def test_score_approval_status_approved():
    """Score >= 80% and factual_accuracy >= 8 is approved."""
    score = Score(
        specificity=8, benefit_coverage=8, keyword_inclusion=8,
        format_adherence=8, brand_voice=8, factual_accuracy=8,
    )
    assert score.composite == 80.0
    assert score.approval_status == "approved"


def test_score_approval_status_rejected_low_accuracy():
    """Factual accuracy < 8 is always rejected."""
    score = Score(
        specificity=10, benefit_coverage=10, keyword_inclusion=10,
        format_adherence=10, brand_voice=10, factual_accuracy=7,
    )
    assert score.composite > 80.0
    assert score.approval_status == "rejected"


def test_score_approval_status_revise():
    """Score 70-79% with factual_accuracy >= 8 needs revision."""
    score = Score(
        specificity=7, benefit_coverage=7, keyword_inclusion=7,
        format_adherence=7, brand_voice=7, factual_accuracy=8,
    )
    # (7+7+7+7+7+8) / 60 * 100 = 43/60 * 100 = 71.67%
    assert 70 <= score.composite < 80
    assert score.approval_status == "revise"


# Task 2.5: Candidate Model Tests
def test_candidate_model_structure():
    """Candidate contains title, description, claims, and scores."""
    claims = [
        Claim(claim="18-inch length", source_field="product_length", source_value="18.0"),
        Claim(claim="solid brass", source_field="material", source_value="Brass"),
    ]
    self_score = Score(
        specificity=8, benefit_coverage=9, keyword_inclusion=7,
        format_adherence=10, brand_voice=8, factual_accuracy=9,
    )
    candidate = Candidate(
        title="Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass",
        description="Crafted from solid brass that will never corrode...",
        claims=claims,
        self_score=self_score,
    )
    assert len(candidate.title) < 150
    assert len(candidate.claims) == 2
    assert candidate.self_score.composite == 85.0


def test_candidate_title_max_length():
    """Title must be <= 150 characters."""
    with pytest.raises(ValueError, match="Title must be <= 150 characters"):
        Candidate(
            title="A" * 151,
            description="Valid description " * 50,
            claims=[],
            self_score=Score(
                specificity=5, benefit_coverage=5, keyword_inclusion=5,
                format_adherence=5, brand_voice=5, factual_accuracy=5,
            ),
        )
