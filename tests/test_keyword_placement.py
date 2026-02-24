import pytest

from feedops.models import Candidate, ParentSKU, Score, Variant
from feedops.pipeline.enrichment import Evidence
from feedops.pipeline.keyword_placement import (
    KeywordPlacementPlan,
    build_keyword_placement_plan,
    validate_candidate_keyword_placement,
    get_canonical_product_type,
    get_room_context,
)


def _make_parent_sku(*, category: str = "Towel Bars", material: str = "Brass") -> ParentSKU:
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        position=1,
    )
    return ParentSKU(
        master_sku="1031/18",
        category=category,
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar...",
        material=material,
        mounting_type="Wall mount",
        variants=[variant],
    )


def _make_candidate(*, title: str, short_title: str, description: str, shopify_title: str) -> Candidate:
    return Candidate(
        google_title=title,
        google_short_title=short_title,
        google_description=description,
        bing_title=title,
        bing_description=description,
        shopify_title=shopify_title,
        shopify_description=f"<p>{description}</p>",
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


def test_build_keyword_placement_plan_prefers_keyword_intent_anchor():
    parent_sku = _make_parent_sku()
    evidence = [
        Evidence(
            field="keyword_intent_master",
            value="wall mount towel bar, bath towel holder",
            source="keyword_intent_master",
        )
    ]

    plan = build_keyword_placement_plan(parent_sku, evidence)

    assert plan.title_anchor == "wall mount towel bar"
    assert "bath towel holder" in plan.description_terms


def test_build_keyword_placement_plan_prefers_search_query_anchor():
    parent_sku = _make_parent_sku()
    evidence = [
        Evidence(
            field="search_queries_top",
            value='"bathroom towel bar wall mount" (2.4K vol), "18 inch towel bar" (1.2K vol)',
            source="search_insights",
        ),
        Evidence(
            field="keyword_intent_master",
            value="solid brass towel bar",
            source="keyword_intent_master",
        ),
    ]

    plan = build_keyword_placement_plan(parent_sku, evidence)

    assert plan.title_anchor == "bathroom towel bar wall mount"
    assert plan.enforce_alignment is True
    assert "18 inch towel bar" in plan.description_terms


def test_build_keyword_placement_plan_distills_noisy_query_fragments():
    parent_sku = _make_parent_sku()
    evidence = [
        Evidence(
            field="search_queries_top",
            value='"if you are searching for bathroom towel bar wall mount" (2.4K vol), "best 18 inch towel bar near me" (1.2K vol)',
            source="search_insights",
        ),
    ]

    plan = build_keyword_placement_plan(parent_sku, evidence)

    assert "searching" not in " ".join(plan.distilled_intent_terms)
    assert "near me" not in " ".join(plan.distilled_intent_terms)
    assert any("towel bar" in term for term in plan.distilled_intent_terms)


def test_build_keyword_placement_plan_filters_material_mismatch():
    parent_sku = _make_parent_sku(material="Brass")
    evidence = [
        Evidence(
            field="keyword_intent_master",
            value="stainless steel towel bar, brass towel bar",
            source="keyword_intent_master",
        )
    ]

    plan = build_keyword_placement_plan(parent_sku, evidence)

    assert plan.title_anchor == "brass towel bar"
    assert all("stainless" not in term.lower() for term in plan.description_terms)


def test_build_keyword_placement_plan_falls_back_when_no_keywords():
    parent_sku = _make_parent_sku()

    plan = build_keyword_placement_plan(parent_sku, [])

    assert plan.title_anchor == "towel bar"


def test_validate_candidate_keyword_placement_flags_missing_anchor_and_terms():
    plan = KeywordPlacementPlan(
        title_anchor="wall mount towel bar",
        short_title_anchor="wall mount towel bar",
        title_support_terms=[],
        description_terms=["bath towel holder"],
        description_min_required=1,
        description_first_150_required=1,
        brand="Allied Brass",
    )
    candidate = _make_candidate(
        title="18-Inch Towel Bar | Allied Brass",
        short_title="18-Inch Towel Bar",
        description="Upgrade your bath with a stylish bar.",
        shopify_title="18-Inch Towel Bar | Allied Brass Extra",
    )

    errors = validate_candidate_keyword_placement(candidate, plan)

    assert any("google_title missing title anchor" in e for e in errors)
    assert any("google_short_title missing title anchor" in e for e in errors)
    assert any("shopify_title must not include Allied Brass" in e for e in errors)
    assert any("google_description missing description term in first 150 chars" in e for e in errors)


def test_validate_candidate_keyword_placement_flags_bing_anti_stuffing():
    plan = KeywordPlacementPlan(
        title_anchor="wall mount towel bar",
        short_title_anchor=None,
        title_support_terms=[],
        description_terms=["bath towel holder"],
        description_min_required=1,
        description_first_150_required=0,
        brand="Allied Brass",
        enforce_alignment=True,
    )
    candidate = _make_candidate(
        title="Wall Mount Towel Bar, Solid Brass, Allied Brass",
        short_title="Wall Mount Towel Bar",
        description=(
            "This towel bar / towel rack (or towel holder) supports multiple sizes: "
            '18 in / 24 in / 30 in for bathroom use.'
        ),
        shopify_title="Wall Mount Towel Bar",
    )

    errors = validate_candidate_keyword_placement(candidate, plan)

    assert any("slash-separated keyword list" in e for e in errors)
    assert any("parenthetical keyword list" in e for e in errors)
    assert any("dimension dump list" in e for e in errors)


# Fix 2.1: Canonical product type tests
def test_get_canonical_product_type_returns_mapping():
    """get_canonical_product_type returns the canonical form for known categories."""
    assert get_canonical_product_type("Towel Bars") == "Towel Bar"
    assert get_canonical_product_type("Grab Bars") == "Grab Bar"
    assert get_canonical_product_type("Make-Up Mirrors") == "Makeup Mirror"
    assert get_canonical_product_type("Unknown Category") is None


# Fix 2.4: Room context tests
def test_get_room_context_returns_kitchen_for_paper_towel_holders():
    """get_room_context returns 'kitchen' for kitchen categories."""
    assert get_room_context("Paper Towel Holders") == "kitchen"
    assert get_room_context("Kitchen Towel Bars") == "kitchen"
    assert get_room_context("Kitchen Accessories") == "kitchen"


def test_get_room_context_returns_bathroom_for_bathroom_categories():
    """get_room_context returns 'bathroom' for bathroom categories."""
    assert get_room_context("Towel Bars") == "bathroom"
    assert get_room_context("Grab Bars") == "bathroom"
    assert get_room_context("Toilet Paper Holders") == "bathroom"


def test_get_room_context_returns_none_for_neutral_categories():
    """get_room_context returns None for room-neutral categories."""
    assert get_room_context("Cabinet Knobs") is None


def test_get_room_context_defaults_to_bathroom_for_unknown():
    """get_room_context defaults to 'bathroom' for unknown categories."""
    assert get_room_context("Unknown Category") == "bathroom"


def test_build_keyword_placement_plan_includes_room_context():
    """build_keyword_placement_plan includes room_context in the plan."""
    parent_sku = _make_parent_sku(category="Towel Bars")
    plan = build_keyword_placement_plan(parent_sku, [])
    assert plan.room_context == "bathroom"

    parent_sku_kitchen = _make_parent_sku(category="Paper Towel Holders")
    plan_kitchen = build_keyword_placement_plan(parent_sku_kitchen, [])
    assert plan_kitchen.room_context == "kitchen"
