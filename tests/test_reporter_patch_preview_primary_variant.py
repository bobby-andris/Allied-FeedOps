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
            factual_accuracy=10,
            specificity=10,
            benefit_coverage=10,
            keyword_inclusion=10,
            format_adherence=10,
            brand_voice=10,
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

