from feedops.models import Candidate, Claim, ParentSKU, Score, Variant
from feedops.pipeline.reporter import generate_variant_patch_preview


def test_google_short_title_prefers_finish_first_when_it_fits(monkeypatch) -> None:
    finish_name = "Unlacquered Brass"
    variant = Variant(
        option_sku="CL-41-24-ULB",
        finish=finish_name,
        finish_code="ULB",
        gmc_id="shopify_US_1_2",
    )
    parent = ParentSKU(
        master_sku="CL-41",
        category="Towel Bars",
        current_title="Current title",
        current_description="Current description",
        variants=[variant],
    )
    candidate = Candidate(
        google_title="24-Inch Wall Mount Towel Bar | Allied Brass",
        google_short_title="24-Inch Wall Mount Towel Bar",
        google_description="Keep towels within reach.\n\nHighlights:\n- Durable\n\nSpecs:\nLength: 24 in\n",
        bing_title="24-Inch Wall Mount Towel Bar | Allied Brass",
        bing_description="desc",
        shopify_title="24-Inch Wall Mount Towel Bar",
        shopify_description="<p>desc</p>",
        shopify_meta_description="desc",
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
        parent_sku=parent,
        variant=variant,
        candidate=candidate,
        platform="google",
    )
    assert patch["short_title"].startswith(finish_name)

