from __future__ import annotations

from feedops.models import Candidate, ParentSKU, Score, Variant
import feedops.pipeline.reporter as reporter


def test_generate_patch_preview_sanitizes_primary_patch_title(monkeypatch) -> None:
    parent = ParentSKU(
        master_sku="FT-16",
        category="Towel Rings",
        collection="Foxtrot",
        current_title="Current",
        current_description="Current",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku="FT-16-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_FT16",
            ),
        ],
    )
    candidate = Candidate(
        google_title="Towel Ring, Solid Brass, Foxtrot, Allied Brass",
        google_short_title="Towel Ring, Allied Brass",
        google_description="Base description.",
        bing_title="Towel Ring, Solid Brass, Foxtrot, Allied Brass",
        bing_description="Base description.",
        shopify_title="Foxtrot Towel Ring, Allied Brass",
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

    def fake_variant_patch_preview(*_args, **_kwargs):
        return {"title": "Towel Ring, Solid Brass, Foxtrot, , Allied Brass"}

    monkeypatch.setattr(reporter, "generate_variant_patch_preview", fake_variant_patch_preview)

    patch = reporter.generate_patch_preview(parent, candidate, platform="bing")

    assert patch["title"] == "Towel Ring, Solid Brass, Foxtrot, Allied Brass"

