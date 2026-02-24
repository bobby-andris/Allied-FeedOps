from feedops.models import Candidate, ParentSKU, Score, Variant
from feedops.pipeline.reporter import generate_patch_preview


def test_shopify_body_html_includes_sanitized_collection_design_notes_for_multi_size_products() -> None:
    parent = ParentSKU(
        master_sku="CL-41",
        category="Towel Bars",
        collection="Argo",
        current_title="Current title",
        current_description="Current description",
        variants=[
            Variant(
                option_sku="CL-41-18-SN",
                finish="Satin Nickel",
                finish_code="SN",
                gmc_id="shopify_US_1_11",
                product_length=18,
            ),
            Variant(
                option_sku="CL-41-24-SN",
                finish="Satin Nickel",
                finish_code="SN",
                gmc_id="shopify_US_1_12",
                product_length=24,
            ),
        ],
    )
    candidate = Candidate(
        google_title="t",
        google_short_title="t",
        google_description="d",
        bing_title="t",
        bing_description="d",
        shopify_title="t",
        shopify_description="<p>Hook.</p><ul><li>Bullet</li></ul>",
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

    patch = generate_patch_preview(parent, candidate, platform="shopify")
    body = patch["body_html"]
    assert "Argo Collection" in body
    assert "Available in" not in body

