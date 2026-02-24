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
    """Composite = sum of all scores / 100 * 100."""
    score = Score(
        hook_quality=8,
        product_specificity=8,
        competitive_diff=8,
        keyword_integration=7,
        customer_scenario=8,
        emotional_resonance=8,
        factual_accuracy=9,
        platform_compliance=10,
        finish_integration=8,
        variety_score=8,
    )
    # (8+8+8+7+8+8+9+10+8+8) / 100 * 100 = 82%
    assert score.composite == 82.0


def test_score_approval_status_approved():
    """Score >= 80% and factual_accuracy >= 8 is approved."""
    score = Score(
        hook_quality=8, product_specificity=8, competitive_diff=8,
        keyword_integration=8, customer_scenario=8, emotional_resonance=8,
        factual_accuracy=8, platform_compliance=8, finish_integration=8,
        variety_score=8,
    )
    assert score.composite == 80.0
    assert score.approval_status == "approved"


def test_score_approval_status_rejected_low_accuracy():
    """Factual accuracy < 8 is always rejected."""
    score = Score(
        hook_quality=10, product_specificity=10, competitive_diff=10,
        keyword_integration=10, customer_scenario=10, emotional_resonance=10,
        factual_accuracy=7, platform_compliance=10, finish_integration=10,
        variety_score=10,
    )
    assert score.composite > 80.0
    assert score.approval_status == "rejected"


def test_score_approval_status_revise():
    """Score 70-79% with factual_accuracy >= 8 needs revision."""
    score = Score(
        hook_quality=7, product_specificity=7, competitive_diff=7,
        keyword_integration=7, customer_scenario=7, emotional_resonance=7,
        factual_accuracy=8, platform_compliance=7, finish_integration=7,
        variety_score=7,
    )
    # (7*9 + 8) / 100 * 100 = 71%
    assert 70 <= score.composite < 80
    assert score.approval_status == "revise"


# Task 2.5: Candidate Model Tests
def test_candidate_model_structure():
    """Candidate contains platform-specific fields, claims, and scores."""
    claims = [
        Claim(claim="18-inch length", source_field="product_length", source_value="18.0"),
        Claim(claim="solid brass", source_field="material", source_value="Brass"),
    ]
    self_score = Score(
        hook_quality=8, product_specificity=9, competitive_diff=7,
        keyword_integration=7, customer_scenario=8, emotional_resonance=8,
        factual_accuracy=9, platform_compliance=10, finish_integration=8,
        variety_score=8,
    )
    candidate = Candidate(
        google_title="ADA-Compliant 18-Inch Grab Bar 500lb Capacity | Solid Brass | Allied Brass",
        google_short_title="18-Inch Grab Bar",
        google_description="Crafted from solid brass that will never corrode..." * 10,
        bing_title="ADA-Compliant 18-Inch Grab Bar (Safety Handle) | Solid Brass | Allied Brass",
        bing_description="Crafted from solid brass that will never corrode..." * 10,
        shopify_title="18-Inch Grab Bar | Allied Brass",
        shopify_description="<p>Crafted from solid brass...</p>",
        claims=claims,
        self_score=self_score,
    )
    assert len(candidate.google_title) < 150
    assert len(candidate.google_short_title) < 70
    assert len(candidate.claims) == 2
    # (8+9+7+7+8+8+9+10+8+8) / 100 * 100 = 82%
    assert candidate.self_score.composite == 82.0


def test_candidate_selection_metadata_defaults_to_none():
    """Selection metadata defaults to None when unset."""
    candidate = Candidate(
        google_title="Valid google title",
        google_short_title="Short title",
        google_description="Valid description " * 50,
        bing_title="Valid bing title",
        bing_description="Valid description " * 50,
        shopify_title="Valid shopify title",
        shopify_description="<p>Valid description</p>",
        claims=[],
        self_score=Score(
            hook_quality=5,
            product_specificity=5,
            competitive_diff=5,
            keyword_integration=5,
            customer_scenario=5,
            emotional_resonance=5,
            factual_accuracy=5,
            platform_compliance=5,
            finish_integration=5,
            variety_score=5,
        ),
    )
    assert candidate.heuristic_score is None
    assert candidate.heuristic_score_breakdown is None
    assert candidate.selection_weights is None
    assert candidate.candidate_index is None
    assert candidate.num_candidates is None


def test_candidate_google_title_max_length():
    """Google title must be <= 150 characters."""
    with pytest.raises(ValueError, match="Google title must be <= 150 characters"):
        Candidate(
            google_title="A" * 151,
            google_short_title="Short title",
            google_description="Valid description " * 50,
            bing_title="Valid bing title",
            bing_description="Valid description " * 50,
            shopify_title="Valid shopify title",
            shopify_description="<p>Valid description</p>",
            claims=[],
            self_score=Score(
                hook_quality=5, product_specificity=5, competitive_diff=5,
                keyword_integration=5, customer_scenario=5, emotional_resonance=5,
                factual_accuracy=5, platform_compliance=5, finish_integration=5,
                variety_score=5,
            ),
        )


def test_candidate_shopify_title_max_length():
    """Shopify title must be <= 255 characters."""
    with pytest.raises(ValueError, match="Shopify title must be <= 255 characters"):
        Candidate(
            google_title="Valid google title",
            google_short_title="Short title",
            google_description="Valid description " * 50,
            bing_title="Valid bing title",
            bing_description="Valid description " * 50,
            shopify_title="B" * 256,
            shopify_description="<p>Valid description</p>",
            claims=[],
            self_score=Score(
                hook_quality=5, product_specificity=5, competitive_diff=5,
                keyword_integration=5, customer_scenario=5, emotional_resonance=5,
                factual_accuracy=5, platform_compliance=5, finish_integration=5,
                variety_score=5,
            ),
        )


def test_candidate_google_short_title_max_length():
    """Google short title must be <= 70 characters."""
    with pytest.raises(ValueError, match="Google short title must be <= 70 characters"):
        Candidate(
            google_title="Valid google title",
            google_short_title="C" * 71,
            google_description="Valid description " * 50,
            bing_title="Valid bing title",
            bing_description="Valid description " * 50,
            shopify_title="Valid shopify title",
            shopify_description="<p>Valid description</p>",
            claims=[],
            self_score=Score(
                hook_quality=5, product_specificity=5, competitive_diff=5,
                keyword_integration=5, customer_scenario=5, emotional_resonance=5,
                factual_accuracy=5, platform_compliance=5, finish_integration=5,
                variety_score=5,
            ),
        )
