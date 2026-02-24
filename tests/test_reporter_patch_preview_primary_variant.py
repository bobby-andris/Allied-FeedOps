from feedops.models import Candidate, ParentSKU, Score, Variant
from feedops.pipeline.reporter import generate_patch_preview


def test_google_patch_preview_uses_primary_variant_offer_and_title() -> None:
    parent = ParentSKU(
        master_sku="CL-41-30",
        category="Towel Bars",
        collection="Carolina",
        current_title="Current",
        current_description="Current",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku="CL-41-18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_18",
            ),
            Variant(
                option_sku="CL-41-30-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_30",
            ),
        ],
    )
    candidate = Candidate(
        google_title="Towel Bar, 30-Inch, Solid Brass, Carolina Collection, , Allied Brass",
        google_short_title="Towel Bar, Solid Brass, Allied Brass",
        google_description="Base description.",
        bing_title="Towel Bar, 30-Inch, Solid Brass, Carolina Collection, , Allied Brass",
        bing_description="Base description.",
        shopify_title="Carolina Collection 30-Inch Towel Bar (Solid Brass) -, Allied Brass",
        shopify_description="<p>Base description.</p>",
        shopify_meta_description="",
        claims=[],
        self_score=Score(
            hook_quality=10, product_specificity=10, competitive_diff=10,
            keyword_integration=10, customer_scenario=10, emotional_resonance=10,
            factual_accuracy=10, platform_compliance=10, finish_integration=10,
            variety_score=10,
        ),
        candidate_index=0,
        num_candidates=1,
    )

    patch = generate_patch_preview(parent, candidate, platform="google")

    # OfferId should align to the requested MasterSKU size when multiple sizes exist.
    assert patch["offerId"] == "shopify_US_1_30"

    # The top-level title should reflect the primary variant (finish + size) and be clean.
    assert patch["title"].startswith("Antique Brass")
    assert ", ," not in patch["title"]
    assert "30" in patch["title"]

