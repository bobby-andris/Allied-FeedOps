from __future__ import annotations

from feedops.models import Candidate, ParentSKU, Score, Variant
from feedops.pipeline.reporter import generate_patch_preview


def _build_parent_and_candidate() -> tuple[ParentSKU, Candidate]:
    parent = ParentSKU(
        master_sku="CL-41-30",
        category="Towel Bars",
        collection="Carolina",
        current_title="Current",
        current_description="Current",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku="CL-41-30-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_30",
            ),
        ],
    )
    candidate = Candidate(
        google_title="Towel Bar, 30-Inch, Solid Brass, Carolina Collection, Allied Brass",
        google_short_title="Towel Bar, Solid Brass, Allied Brass",
        google_description="Base description.",
        bing_title="Towel Bar, 30-Inch, Solid Brass, Carolina Collection, Allied Brass",
        bing_description="Base description.",
        shopify_title="Carolina Collection 30-Inch Towel Bar (Solid Brass), Allied Brass",
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
    return parent, candidate


def test_reporter_google_patch_structured_only_omits_standard_fields(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_GMC_STRUCTURED_ONLY", "true")
    parent, candidate = _build_parent_and_candidate()

    patch = generate_patch_preview(parent, candidate, platform="google")

    assert "structured_title" in patch
    assert "structured_description" in patch
    assert patch["structured_title"]["content"]
    assert patch["structured_description"]["content"]

    assert "title" not in patch
    assert "description" not in patch

