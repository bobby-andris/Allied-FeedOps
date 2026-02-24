import re

from feedops.models import Candidate, ParentSKU, Variant
from feedops.models.score import Score
from feedops.pipeline.reporter import generate_variant_patch_preview


def _candidate_for_titles(google_title: str) -> Candidate:
    # Minimal candidate object needed for reporter helpers
    return Candidate(
        google_title=google_title,
        google_short_title="Robe Hook, Solid Brass, Allied Brass",
        google_description="Base description.",
        bing_title=google_title,
        bing_description="Base description.",
        shopify_title=google_title,
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


def test_variant_title_does_not_inject_single_size_series_number():
    parent = ParentSKU(
        master_sku="SH-84",
        category="Towel Stands",
        collection="Assorted Free Standing Accessories",
        current_title="Towel Stand With 4 Pivoting Swing Arms 49-Inch Solid Brass Freestanding",
        current_description="Description.",
        material="Brass",
        variants=[
            Variant(
                option_sku="SH-84-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
            ),
            Variant(
                option_sku="SH-84-ABZ",
                finish="Antique Bronze",
                finish_code="ABZ",
                gmc_id="shopify_US_1_2",
            ),
        ],
    )
    candidate = _candidate_for_titles(
        "Freestanding 4-Arm Swing Towel Stand, Solid Brass, 49-Inch, Allied Brass"
    )
    patch = generate_variant_patch_preview(
        parent_sku=parent,
        variant=parent.variants[0],
        candidate=candidate,
        platform="google",
    )
    assert "84-Inch" not in patch["title"]


def test_variant_title_does_not_corrupt_decimal_dimensions_with_series_size():
    parent = ParentSKU(
        master_sku="MB-20",
        category="Robe Hooks",
        collection="Malibu",
        current_title="Robe Hook",
        current_description="Description.",
        material="Brass",
        variants=[
            Variant(
                option_sku="MB-20-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_2_1",
            ),
            Variant(
                option_sku="MB-20-ABZ",
                finish="Antique Bronze",
                finish_code="ABZ",
                gmc_id="shopify_US_2_2",
            ),
        ],
    )
    candidate = _candidate_for_titles(
        "Robe Hook, 2.64-Inch, Solid Brass, Malibu Collection, Allied Brass"
    )
    patch = generate_variant_patch_preview(
        parent_sku=parent,
        variant=parent.variants[0],
        candidate=candidate,
        platform="google",
    )
    assert "2.64-Inch" in patch["title"]
    assert re.search(r"\b2\.20-Inch\b", patch["title"]) is None
